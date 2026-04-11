#!/bin/bash

# 顏色定義
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🚀 Termux yt-dlp 終極下載器 一鍵部署腳本${NC}"
echo -e "${BLUE}========================================${NC}"

# 1. 請求存取權限
echo -e "${BLUE}[1/5] 請求手機存取權限...${NC}"
termux-setup-storage
sleep 2

# 2. 更新系統並安裝基礎依賴
echo -e "${BLUE}[2/5] 更新系統並安裝基礎依賴...${NC}"
pkg update -y && pkg upgrade -y
pkg install python ffmpeg pigz openssh -y

# 3. 安裝 Python 依賴
echo -e "${BLUE}[3/5] 安裝 Python 依賴 (Flask, yt-dlp)...${NC}"
pip install yt-dlp flask flask-cors

# 4. 確保下載目錄存在
echo -e "${BLUE}[4/5] 建立下載目錄...${NC}"
mkdir -p /sdcard/Download/temp

# 5. 啟動伺服器與內網穿透
echo -e "${BLUE}[5/5] 啟動伺服器...${NC}"
echo -e "${GREEN}提示：伺服器啟動後，請開啟另一個 Termux 視窗並執行：${NC}"
echo -e "${GREEN}ssh -R 80:localhost:5000 serveo.net${NC}"
echo -e "${GREEN}獲取公開 URL 後，填入 GitHub 前端介面即可開始下載！${NC}"

python server.py
