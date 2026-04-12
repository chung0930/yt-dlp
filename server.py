import os
import subprocess
import sys
import json
import threading
import time
import re
import shutil
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_PATH = "/sdcard/Download"
TEMP_PATH = "/sdcard/Download/temp"
LOG_FILE = "/sdcard/Download/error_report.log"
TASKS = {}

# 設定日誌
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_error(msg):
    logging.error(msg)
    print(f"ERROR: {msg}")

def log_info(msg):
    logging.info(msg)
    print(f"INFO: {msg}")

# 設定 Termux 環境變數路徑 (這點對 Termux 非常重要)
TERMUX_BIN = "/data/data/com.termux/files/usr/bin"
os.environ["PATH"] = f"{TERMUX_BIN}:{os.environ.get('PATH', '')}"

# 啟動時檢查依賴
def check_dependencies():
    deps = ["yt-dlp", "ffmpeg", "ffprobe", "zip"]
    missing = []
    for dep in deps:
        if shutil.which(dep) is None:
            # 嘗試在 Termux 標準路徑找
            if not os.path.exists(os.path.join(TERMUX_BIN, dep)):
                missing.append(dep)
    if missing:
        log_error(f"Missing dependencies: {', '.join(missing)}. Please run pkg install yt-dlp ffmpeg zip")
    else:
        log_info("All dependencies checked and found.")

check_dependencies()

# 自動清理任務 (每天凌晨 3 點執行)
def auto_cleanup():
    while True:
        try:
            now = time.localtime()
            if now.tm_hour == 3 and now.tm_min == 0:
                log_info("Running scheduled cleanup...")
                if os.path.exists(TEMP_PATH):
                    shutil.rmtree(TEMP_PATH)
                    os.makedirs(TEMP_PATH)
                time.sleep(60)
            time.sleep(30)
        except Exception as e:
            log_error(f"Cleanup failed: {str(e)}")

threading.Thread(target=auto_cleanup, daemon=True).start()

# 網址拆分功能
def extract_urls(raw_text):
    processed = raw_text.replace('https://', '\nhttps://').replace('http://', '\nhttp://')
    pattern = r'(https?://(?:music\.youtube\.com|www\.youtube\.com|youtu\.be)/[^\s\n\r]+)'
    urls = re.findall(pattern, processed)
    return list(dict.fromkeys(urls))

# 核心下載邏輯
def download_task(task_id, mode, url):
    TASKS[task_id]['status'] = 'processing'
    error_output = [] # 用於捕捉詳細錯誤訊息
    try:
        if not os.path.exists(TEMP_PATH): os.makedirs(TEMP_PATH)
        task_dir = os.path.join(TEMP_PATH, task_id)
        os.makedirs(task_dir)

        # 1. 獲取標題
        log_info(f"Task {task_id}: Fetching info for URL: {url}")
        info_cmd = ["yt-dlp", "--get-filename", "-o", "%(playlist_title,title)s", url]
        result = subprocess.run(info_cmd, capture_output=True, text=True, env=os.environ)
        raw_name = result.stdout.strip().split('\n')[0]
        safe_name = re.sub(r'[\\/*?:"<>|]', "", raw_name) or f"download_{task_id}"
        log_info(f"Task {task_id}: Target safe name: {safe_name}")

        # 2. 構建下載指令
        cmd = ["yt-dlp", "--newline", "--progress", "--non-interactive"]
        
        # 輸出模板
        if mode in ["2", "4"]: # 單一檔案
            output_tmpl = os.path.join(task_dir, "%(title)s.%(ext)s")
        else: # 播放清單/專輯
            output_tmpl = os.path.join(task_dir, "%(playlist_index)02d - %(title)s.%(ext)s")

        if mode in ["1", "2", "3"]: # 音樂模式
            cmd += [
                "-x", "--audio-format", "mp3", "--audio-quality", "320k",
                "--embed-thumbnail", "--add-metadata"
            ]
            # 針對 Termux 環境，採用最安全的封面處理參數
            cmd += ["--ppa", "ThumbnailsConvertor:-vf crop=ih:ih"]
            
            if mode in ["1", "3"]: cmd += ["--yes-playlist"]
            if mode == "1": cmd += ["--parse-metadata", "playlist_index:%(track_number)s"]
        
        elif mode in ["4", "5"]: # 影片模式
            cmd += [
                "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best",
                "--merge-output-format", "mp4"
            ]
            if mode == "5": cmd += ["--yes-playlist"]

        cmd += ["-o", output_tmpl, url]

        log_info(f"Task {task_id}: Executing cmd: {' '.join(cmd)}")
        # 啟動子程序，同時捕捉 stdout 和 stderr
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=os.environ)
        
        for line in process.stdout:
            # 解析進度
            match = re.search(r'(\d+\.\d+)%', line)
            if match: TASKS[task_id]['progress'] = match.group(1)
            
            speed_match = re.search(r'at\s+([\d\.]+\w+/s)', line)
            if speed_match: TASKS[task_id]['speed'] = speed_match.group(1)
            
            eta_match = re.search(r'ETA\s+(\d+:\d+)', line)
            if eta_match: TASKS[task_id]['eta'] = eta_match.group(1)
            
            # 記錄所有輸出，以便在出錯時診斷
            error_output.append(line.strip())
            if len(error_output) > 50: error_output.pop(0) # 只保留最後 50 行

        process.wait()
        
        if process.returncode != 0:
            # 如果失敗，將最後的 stderr 輸出作為錯誤原因
            full_error = "\n".join(error_output[-5:])
            raise Exception(f"yt-dlp exited with code {process.returncode}. Detail: {full_error}")

        # 3. 處理下載後的檔案
        files = os.listdir(task_dir)
        if not files: raise Exception("No files found after download.")

        log_info(f"Task {task_id}: Download finished. Preparing delivery...")

        if len(files) > 1 or mode in ["1", "3", "5"]:
            archive_name = f"{safe_name}.zip"
            archive_path = os.path.join(TEMP_PATH, archive_name)
            subprocess.run(["zip", "-r", "-j", archive_path, task_dir], env=os.environ)
            TASKS[task_id]['file'] = archive_name
        else:
            final_ext = os.path.splitext(files[0])[1]
            final_name = f"{safe_name}{final_ext}"
            os.rename(os.path.join(task_dir, files[0]), os.path.join(TEMP_PATH, final_name))
            TASKS[task_id]['file'] = final_name

        TASKS[task_id]['status'] = 'completed'
        TASKS[task_id]['progress'] = '100'
        if os.path.exists(task_dir): shutil.rmtree(task_dir)

    except Exception as e:
        log_error(f"Task {task_id} failed: {str(e)}")
        TASKS[task_id]['status'] = 'failed'
        # 將詳細錯誤回傳給前端
        TASKS[task_id]['error'] = str(e)

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    raw_url = data.get('url', '')
    mode = data.get('mode', '1')
    urls = extract_urls(raw_url)
    if not urls: return jsonify({'error': 'No valid URLs found'}), 400
    
    task_ids = []
    for url in urls:
        task_id = f"{int(time.time())}{len(task_ids)}"
        TASKS[task_id] = {'status': 'pending', 'progress': '0', 'speed': '0', 'eta': '0', 'url': url}
        threading.Thread(target=download_task, args=(task_id, mode, url)).start()
        task_ids.append(task_id)
        time.sleep(0.01)
    return jsonify({'task_ids': task_ids})

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    return jsonify(TASKS.get(task_id, {'status': 'not_found'}))

@app.route('/files/<path:filename>', methods=['GET'])
def get_file(filename):
    return send_from_directory(TEMP_PATH, filename, as_attachment=True)

@app.route('/error_report', methods=['GET'])
def get_error_report():
    if os.path.exists(LOG_FILE):
        return send_from_directory(os.path.dirname(LOG_FILE), os.path.basename(LOG_FILE))
    return "No errors reported yet."

if __name__ == "__main__":
    if not os.path.exists(BASE_PATH): os.makedirs(BASE_PATH)
    if not os.path.exists(TEMP_PATH): os.makedirs(TEMP_PATH)
    log_info("Server v2.4 Debug Version Started.")
    app.run(host='0.0.0.0', port=5000, threaded=True)
