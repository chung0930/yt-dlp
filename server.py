import os
import subprocess
import sys
import json
import threading
import time
import re
import shutil
import logging
from flask import Flask, request, jsonify, send_from_directory, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_PATH = "/sdcard/Download"
TEMP_PATH = "/sdcard/Download/temp"
LOG_FILE = "/sdcard/Download/error_report.log"
TASKS = {}

# 設定日誌
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_error(msg):
    logging.error(msg)
    print(f"ERROR: {msg}")

# 自動清理任務 (每天執行一次)
def auto_cleanup():
    while True:
        try:
            now = time.localtime()
            # 每天凌晨 3 點執行清理
            if now.tm_hour == 3 and now.tm_min == 0:
                print("Running scheduled cleanup...")
                if os.path.exists(TEMP_PATH):
                    shutil.rmtree(TEMP_PATH)
                    os.makedirs(TEMP_PATH)
                time.sleep(60) # 避免重複執行
            time.sleep(30)
        except Exception as e:
            log_error(f"Cleanup failed: {str(e)}")

threading.Thread(target=auto_cleanup, daemon=True).start()

# 下載進度解析
def progress_hook(d):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%').replace('%','').strip()
        s = d.get('_speed_str', 'N/A')
        t = d.get('_eta_str', 'N/A')
        task_id = d.get('info_dict', {}).get('task_id')
        if task_id and task_id in TASKS:
            TASKS[task_id]['progress'] = p
            TASKS[task_id]['speed'] = s
            TASKS[task_id]['eta'] = t

# 核心下載邏輯
def download_task(task_id, mode, url):
    TASKS[task_id]['status'] = 'processing'
    try:
        if not os.path.exists(TEMP_PATH): os.makedirs(TEMP_PATH)
        task_dir = os.path.join(TEMP_PATH, task_id)
        os.makedirs(task_dir)

        # 獲取標題/清單名稱作為檔名
        info_cmd = ["yt-dlp", "--get-filename", "-o", "%(playlist_title,title)s", url]
        result = subprocess.run(info_cmd, capture_output=True, text=True)
        raw_name = result.stdout.strip().split('\n')[0]
        safe_name = re.sub(r'[\\/*?:"<>|]', "", raw_name) or "download"

        output_tmpl = os.path.join(task_dir, "%(playlist_index)02d - %(title)s.%(ext)s")
        if mode == "2" or mode == "4":
            output_tmpl = os.path.join(task_dir, "%(title)s.%(ext)s")

        cmd = ["yt-dlp", "--newline", "--progress", "--non-interactive"]
        
        if mode in ["1", "2", "3"]: # 音樂模式
            cmd += [
                "-x", "--audio-format", "mp3", "--audio-quality", "320k",
                "--embed-thumbnail", "--add-metadata",
                "--ppa", "ThumbnailsConvertor: -c:v mjpeg -vf crop='ih:ih'",
            ]
            if mode in ["1", "3"]: cmd += ["--yes-playlist"]
            if mode == "1": cmd += ["--parse-metadata", "playlist_index:%(track_number)s"]
        
        elif mode in ["4", "5"]: # 影片模式
            cmd += [
                "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best",
                "--merge-output-format", "mp4",
                "--postprocessor-args", "ffmpeg: -c:v copy -c:a aac",
            ]
            if mode == "5": cmd += ["--yes-playlist"]

        cmd += ["-o", output_tmpl, url]

        # 執行下載並獲取即時進度
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            # 解析進度 [download]  10.0% of 10.00MiB at  1.00MiB/s ETA 00:01
            match = re.search(r'(\d+\.\d+)%', line)
            if match:
                TASKS[task_id]['progress'] = match.group(1)
            speed_match = re.search(r'at\s+([\d\.]+\w+/s)', line)
            if speed_match:
                TASKS[task_id]['speed'] = speed_match.group(1)
            eta_match = re.search(r'ETA\s+(\d+:\d+)', line)
            if eta_match:
                TASKS[task_id]['eta'] = eta_match.group(1)

        process.wait()
        
        if process.returncode != 0:
            raise Exception(f"yt-dlp exited with code {process.returncode}")

        files = os.listdir(task_dir)
        if not files:
            raise Exception("No files downloaded.")

        if len(files) > 1 or mode in ["1", "3", "5"]:
            archive_name = f"{safe_name}.zip"
            archive_path = os.path.join(TEMP_PATH, archive_name)
            # 使用 zip 命令進行壓縮，解決重連問題
            subprocess.run(["zip", "-r", "-j", archive_path, task_dir])
            TASKS[task_id]['file'] = archive_name
        else:
            final_name = files[0]
            os.rename(os.path.join(task_dir, final_name), os.path.join(TEMP_PATH, final_name))
            TASKS[task_id]['file'] = final_name

        TASKS[task_id]['status'] = 'completed'
        TASKS[task_id]['progress'] = '100'
        shutil.rmtree(task_dir) # 下載完成後刪除暫存資料夾

    except Exception as e:
        log_error(f"Task {task_id} failed: {str(e)}")
        TASKS[task_id]['status'] = 'failed'
        TASKS[task_id]['error'] = str(e)

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    mode = data.get('mode')
    if not url: return jsonify({'error': 'No URL'}), 400
    task_id = str(int(time.time()))
    TASKS[task_id] = {'status': 'pending', 'progress': '0', 'speed': '0', 'eta': '0'}
    threading.Thread(target=download_task, args=(task_id, mode, url)).start()
    return jsonify({'task_id': task_id})

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
    app.run(host='0.0.0.0', port=5000, threaded=True)
