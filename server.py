import os
import subprocess
import sys
import json
import threading
import time
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_PATH = "/sdcard/Download"
TEMP_PATH = "/sdcard/Download/temp"
TASKS = {}

# 自動安裝依賴
def install_dependencies():
    print("Checking and installing dependencies...")
    commands = [
        "pkg update -y",
        "pkg install python ffmpeg -y",
        "pkg install pigz -y",
        "pip install yt-dlp flask flask-cors"
    ]
    for cmd in commands:
        subprocess.run(cmd, shell=True)

# 下載進度解析
def progress_hook(d):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%').replace('%','')
        s = d.get('_speed_str', 'N/A')
        t = d.get('_eta_str', 'N/A')
        task_id = d.get('info_dict', {}).get('task_id')
        if task_id:
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

        common_opts = {
            'progress_hooks': [progress_hook],
            'logger': MyLogger(task_id),
            'info_dict': {'task_id': task_id}
        }

        if mode == "1": # YouTube Music 專輯
            output = os.path.join(task_dir, "%(playlist_index)02d - %(title)s.%(ext)s")
            cmd = [
                "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "320k",
                "--embed-thumbnail", "--add-metadata", "--yes-playlist",
                "--parse-metadata", "playlist_index:%(track_number)s",
                "--ppa", "ThumbnailsConvertor: -c:v mjpeg -vf crop='ih:ih'",
                "-o", output, url
            ]
        elif mode == "2": # YouTube Music 單曲
            output = os.path.join(task_dir, "%(title)s.%(ext)s")
            cmd = [
                "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "320k",
                "--embed-thumbnail", "--add-metadata",
                "--ppa", "ThumbnailsConvertor: -c:v mjpeg -vf crop='ih:ih'",
                "-o", output, url
            ]
        elif mode == "3": # YouTube Music 播放清單 (不分專輯)
            output = os.path.join(task_dir, "%(playlist_index)02d - %(title)s.%(ext)s")
            cmd = [
                "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "320k",
                "--embed-thumbnail", "--add-metadata", "--yes-playlist",
                "--ppa", "ThumbnailsConvertor: -c:v mjpeg -vf crop='ih:ih'",
                "-o", output, url
            ]
        elif mode == "4": # YouTube 影片 1080p
            output = os.path.join(task_dir, "%(title)s.%(ext)s")
            cmd = [
                "yt-dlp", "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best",
                "--merge-output-format", "mp4",
                "--postprocessor-args", "ffmpeg: -c:v copy -c:a aac",
                "-o", output, url
            ]
        elif mode == "5": # YouTube 影片播放清單
            output = os.path.join(task_dir, "%(playlist_index)02d - %(title)s.%(ext)s")
            cmd = [
                "yt-dlp", "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best",
                "--merge-output-format", "mp4", "--yes-playlist",
                "--postprocessor-args", "ffmpeg: -c:v copy -c:a aac",
                "-o", output, url
            ]

        subprocess.run(cmd)
        
        # 檢查檔案數量決定是否打包
        files = os.listdir(task_dir)
        if len(files) > 3 or mode in ["1", "3", "5"]:
            archive_name = f"{task_id}.tar.gz"
            archive_path = os.path.join(TEMP_PATH, archive_name)
            subprocess.run(f"tar -cf - -C {task_dir} . | pigz > {archive_path}", shell=True)
            TASKS[task_id]['file'] = archive_name
            TASKS[task_id]['is_archive'] = True
        else:
            TASKS[task_id]['file'] = files[0]
            TASKS[task_id]['is_archive'] = False
            # 將單一檔案移出子目錄方便下載
            os.rename(os.path.join(task_dir, files[0]), os.path.join(TEMP_PATH, files[0]))

        TASKS[task_id]['status'] = 'completed'
        TASKS[task_id]['progress'] = '100'
    except Exception as e:
        TASKS[task_id]['status'] = 'failed'
        TASKS[task_id]['error'] = str(e)

class MyLogger:
    def __init__(self, task_id): self.task_id = task_id
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): TASKS[self.task_id]['error'] = msg

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    mode = data.get('mode')
    task_id = str(int(time.time()))
    TASKS[task_id] = {'status': 'pending', 'progress': '0', 'speed': '0', 'eta': '0'}
    threading.Thread(target=download_task, args=(task_id, mode, url)).start()
    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    return jsonify(TASKS.get(task_id, {'status': 'not_found'}))

@app.route('/files/<filename>', methods=['GET'])
def get_file(filename):
    return send_from_directory(TEMP_PATH, filename)

if __name__ == "__main__":
    if not os.path.exists(BASE_PATH): os.makedirs(BASE_PATH)
    if not os.path.exists(TEMP_PATH): os.makedirs(TEMP_PATH)
    # install_dependencies() # 首次執行時解除註解
    app.run(host='0.0.0.0', port=5000)
