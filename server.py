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

# 設定 Termux 環境變數路徑 (這對所有 Termux 指令至關重要)
TERMUX_BIN = "/data/data/com.termux/files/usr/bin"
os.environ["PATH"] = f"{TERMUX_BIN}:{os.environ.get('PATH', '')}"

# 啟動時自動檢查依賴
def check_dependencies():
    deps = ["yt-dlp", "ffmpeg", "ffprobe", "zip"]
    for dep in deps:
        if shutil.which(dep) is None:
            log_info(f"Checking {dep} in Termux path...")
            if not os.path.exists(os.path.join(TERMUX_BIN, dep)):
                log_error(f"Missing {dep}. Please run: pkg install {dep} -y")
    
    # 檢查 Python 套件
    try:
        import flask
        import flask_cors
        import yt_dlp
    except ImportError as e:
        log_error(f"Missing Python package: {e}. Please run: pip install flask flask-cors yt-dlp")

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

# 核心下載邏輯 (v2.6 Ultimate 穩定邏輯)
def download_task(task_id, mode, url):
    TASKS[task_id]['status'] = 'processing'
    error_output = []
    try:
        if not os.path.exists(TEMP_PATH): os.makedirs(TEMP_PATH)
        task_dir = os.path.join(TEMP_PATH, task_id)
        os.makedirs(task_dir)

        # 1. 獲取專輯/清單標題
        pl_cmd = ["yt-dlp", "--get-filename", "-o", "%(playlist_title,title)s", url]
        pl_result = subprocess.run(pl_cmd, capture_output=True, text=True, env=os.environ)
        raw_pl_name = pl_result.stdout.strip().split('\n')[0]
        safe_pl_name = re.sub(r'[\\/*?:"<>|]', "", raw_pl_name) or f"download_{task_id}"

        # 2. 極簡路徑下載 (避開 Android 檔案系統限制)
        cmd = ["yt-dlp", "--newline", "--progress"]
        output_tmpl = os.path.join(task_dir, "track_%(playlist_index)03d.%(ext)s")
        if mode in ["2", "4"]: output_tmpl = os.path.join(task_dir, "single_track.%(ext)s")

        if mode in ["1", "2", "3"]: # 音樂模式
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "320k", "--embed-thumbnail", "--add-metadata", "--ppa", "ThumbnailsConvertor:-vf crop=ih:ih"]
            if mode in ["1", "3"]: cmd += ["--yes-playlist"]
            if mode == "1": cmd += ["--parse-metadata", "playlist_index:%(track_number)s"]
        elif mode in ["4", "5"]: # 影片模式
            cmd += ["-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best", "--merge-output-format", "mp4"]
            if mode == "5": cmd += ["--yes-playlist"]

        cmd += ["-o", output_tmpl, url]
        log_info(f"Task {task_id}: Executing {url}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=os.environ)
        
        for line in process.stdout:
            match = re.search(r'(\d+\.\d+)%', line)
            if match: TASKS[task_id]['progress'] = match.group(1)
            speed_match = re.search(r'at\s+([\d\.]+\w+/s)', line)
            if speed_match: TASKS[task_id]['speed'] = speed_match.group(1)
            eta_match = re.search(r'ETA\s+(\d+:\d+)', line)
            if eta_match: TASKS[task_id]['eta'] = eta_match.group(1)
            error_output.append(line.strip())
            if len(error_output) > 20: error_output.pop(0)

        process.wait()
        if process.returncode != 0:
            full_error = "\n".join(error_output[-5:])
            raise Exception(f"yt-dlp exited with code {process.returncode}. Detail: {full_error}")

        # 3. 安全重新命名
        title_cmd = ["yt-dlp", "--get-filename", "-o", "%(playlist_index)03d|%(title)s", url]
        title_result = subprocess.run(title_cmd, capture_output=True, text=True, env=os.environ)
        title_map = {}
        for line in title_result.stdout.strip().split('\n'):
            if '|' in line:
                idx, title = line.split('|', 1)
                title_map[idx] = re.sub(r'[\\/*?:"<>|]', "", title)

        downloaded_files = os.listdir(task_dir)
        for f in downloaded_files:
            ext = os.path.splitext(f)[1]
            if f.startswith("track_"):
                idx = f.replace("track_", "").replace(ext, "")
                if idx in title_map:
                    new_name = f"{idx} - {title_map[idx]}{ext}"
                    os.rename(os.path.join(task_dir, f), os.path.join(task_dir, new_name))
            elif f == f"single_track{ext}":
                st_cmd = ["yt-dlp", "--get-filename", "-o", "%(title)s", url]
                st_result = subprocess.run(st_cmd, capture_output=True, text=True, env=os.environ)
                st_name = re.sub(r'[\\/*?:"<>|]', "", st_result.stdout.strip())
                os.rename(os.path.join(task_dir, f), os.path.join(task_dir, f"{st_name}{ext}"))

        # 4. 打包 ZIP
        files = os.listdir(task_dir)
        if len(files) > 1 or mode in ["1", "3", "5"]:
            archive_name = f"{safe_pl_name}.zip"
            archive_path = os.path.join(TEMP_PATH, archive_name)
            try:
                subprocess.run(["zip", "-r", "-j", archive_path, task_dir], check=True, env=os.environ)
            except:
                import zipfile
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for root, dirs, filenames in os.walk(task_dir):
                        for filename in filenames:
                            z.write(os.path.join(root, filename), filename)
            TASKS[task_id]['file'] = archive_name
        else:
            final_name = files[0]
            os.rename(os.path.join(task_dir, final_name), os.path.join(TEMP_PATH, final_name))
            TASKS[task_id]['file'] = final_name

        TASKS[task_id]['status'] = 'completed'
        TASKS[task_id]['progress'] = '100'
        if os.path.exists(task_dir): shutil.rmtree(task_dir)

    except Exception as e:
        log_error(f"Task {task_id} failed: {str(e)}")
        TASKS[task_id]['status'] = 'failed'
        TASKS[task_id]['error'] = str(e)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'online', 'version': '3.2 Stable'})

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
    log_info("Server v3.2 Stable Started.")
    app.run(host='0.0.0.0', port=5000, threaded=True)
