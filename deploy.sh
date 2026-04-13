#!/bin/bash

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🚀 Termux yt-dlp 遠端控制中心 v3.0 部署中...${NC}"
echo -e "${BLUE}========================================${NC}"

# 1. 要求儲存權限
echo -e "${YELLOW}[1/5] 正在要求儲存權限，請在手機彈窗點擊「允許」...${NC}"
termux-setup-storage
sleep 3

# 2. 更新系統與安裝依賴
echo -e "${YELLOW}[2/5] 正在安裝系統依賴 (Python, yt-dlp, ffmpeg, zip, ttyd)...${NC}"
pkg update -y && pkg upgrade -y
pkg install python ffmpeg zip ttyd openssh -y
pip install --upgrade pip
pip install flask flask-cors yt-dlp

# 3. 建立下載目錄
echo -e "${YELLOW}[3/5] 正在建立下載目錄...${NC}"
mkdir -p /sdcard/Download/temp

# 4. 準備後端服務
echo -e "${YELLOW}[4/5] 正在準備後端服務...${NC}"
if [ ! -f "server.py" ]; then
    echo -e "${RED}錯誤: 找不到 server.py，請確保 server.py 與此腳本在同一目錄下。${NC}"
    exit 1
fi

# 5. 提示使用者如何啟動
echo -e "${GREEN}[5/5] ✅ 部署完成！${NC}"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${GREEN}1. 啟動後端服務：${NC}"
echo -e "   python server.py"
echo -e ""
echo -e "${GREEN}2. 啟動遠端控制台 (TTYD)：${NC}"
echo -e "   ttyd -p 8080 bash"
echo -e ""
echo -e "${GREEN}3. 啟動內網穿透 (Serveo)：${NC}"
echo -e "   ssh -R 80:localhost:5000 -R 8080:localhost:8080 serveo.net"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${YELLOW}請記下 Serveo 提供給您的兩個網址，並填入前端介面中。${NC}"

# 自動啟動 server.py
echo -e "${YELLOW}正在為您啟動後端服務...${NC}"
python server.py
