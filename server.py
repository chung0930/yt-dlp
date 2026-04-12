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
    # 先處理換行，確保 https 前有間隔
    processed = raw_text.replace('https://', '\nhttps://').replace('http://', '\nhttp://')
    # 匹配 YouTube 和 YouTube Music 連結
    pattern = r'(https?://(?:music\.youtube\.com|www\.youtube\.com|youtu\.be)/[^\s\n\r]+)'
    urls = re.findall(pattern, processed)
    # 移除重複並保持順序
    return list(dict.fromkeys(urls))

# 核心下載邏輯
def download_task(task_id, mode, url):
    TASKS[task_id]['status'] = 'processing'
    try:
        if not os.path.exists(TEMP_PATH): os.makedirs(TEMP_PATH)
        task_dir = os.path.join(TEMP_PATH, task_id)
        os.makedirs(task_dir)

        # 獲取標題
        log_info(f"Task {task_id}: Fetching info for URL: {url}")
        info_cmd = ["yt-dlp", "--get-filename", "-o", "%(playlist_title,title)s", url]
        result = subprocess.run(info_cmd, capture_output=True, text=True)
        raw_name = result.stdout.strip().split('\n')[0]
        safe_name = re.sub(r'[\\/*?:"<>|]', "", raw_name) or "download"
        log_info(f"Task {task_id}: Target name: {safe_name}")

        # 下載指令構建
        cmd = ["yt-dlp", "--newline", "--progress", "--non-interactive"]
        
        # 輸出模板
        output_tmpl = os.path.join(task_dir, "%(playlist_index)02d - %(title)s.%(ext)s")
        if mode in ["2", "4"]: # 單曲或單影片模式
            output_tmpl = os.path.join(task_dir, "%(title)s.%(ext)s")

        if mode in ["1", "2", "3"]: # 音樂模式
            cmd += [
                "-x", "--audio-format", "mp3", "--audio-quality", "320k",
                "--embed-thumbnail", "--add-metadata",
                # 使用最簡單的 ffmpeg 參數，避免引號引發 code 2
                "--postprocessor-args", "ffmpeg:-vf crop=ih:ih"
            ]
            if mode in ["1", "3"]: cmd += ["--yes-playlist"]
            if mode == "1": cmd += ["--parse-metadata", "playlist_index:%(track_number)s"]
        
        elif mode in ["4", "5"]: # 影片模式
            cmd += [
                "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best",
                "--merge-output-format", "mp4",
                "--postprocessor-args", "ffmpeg:-c:v copy -c:a aac"
            ]
            if mode == "5": cmd += ["--yes-playlist"]

        cmd += ["-o", output_tmpl, url]

        log_info(f"Task {task_id}: Executing cmd: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        for line in process.stdout:
            # 解析進度
            match = re.search(r'(\d+\.\d+)%', line)
            if match: TASKS[task_id]['progress'] = match.group(1)
            
            speed_match = re.search(r'at\s+([\d\.]+\w+/s)', line)
            if speed_match: TASKS[task_id]['speed'] = speed_match.group(1)
            
            eta_match = re.search(r'ETA\s+(\d+:\d+)', line)
            if eta_match: TASKS[task_id]['eta'] = eta_match.group(1)

        process.wait()
        
        if process.returncode != 0:
            # 發生錯誤時嘗試獲取最後幾行日誌
            raise Exception(f"yt-dlp exited with code {process.returncode}")

        files = os.listdir(task_dir)
        if not files: raise Exception("No files found after download.")

        log_info(f"Task {task_id}: Downloaded {len(files)} files. Preparing delivery...")

        # 決定傳回方式
        if len(files) > 1 or mode in ["1", "3", "5"]:
            archive_name = f"{safe_name}.zip"
            archive_path = os.path.join(TEMP_PATH, archive_name)
            # 使用 zip 命令進行壓縮
            subprocess.run(["zip", "-r", "-j", archive_path, task_dir])
            TASKS[task_id]['file'] = archive_name
        else:
            final_name = files[0]
            os.rename(os.path.join(task_dir, final_name), os.path.join(TEMP_PATH, final_name))
            TASKS[task_id]['file'] = final_name

        TASKS[task_id]['status'] = 'completed'
        TASKS[task_id]['progress'] = '100'
        shutil.rmtree(task_dir) # 清理暫存資料夾

    except Exception as e:
        log_error(f"Task {task_id} failed: {str(e)}")
        TASKS[task_id]['status'] = 'failed'
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
        # 生成唯一 Task ID
        task_id = f"{int(time.time())}{len(task_ids)}"
        TASKS[task_id] = {'status': 'pending', 'progress': '0', 'speed': '0', 'eta': '0', 'url': url}
        threading.Thread(target=download_task, args=(task_id, mode, url)).start()
        task_ids.append(task_id)
        time.sleep(0.05) # 微調避免 ID 衝突
        
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
    log_info("Server v2.2 started. One-time fix for code 2 and URL splitter.")
    app.run(host='0.0.0.0', port=5000, threaded=True)
