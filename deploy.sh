#!/bin/bash

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🚀 Termux yt-dlp 遠端控制中心 v3.2 部署中...${NC}"
echo -e "${GREEN}✨ 穩定相容版 (Fixed-URL + Stable-Pip)${NC}"
echo -e "${BLUE}========================================${NC}"

# 1. 要求儲存權限
echo -e "${YELLOW}[1/5] 正在要求儲存權限，請在手機彈窗點擊「允許」...${NC}"
termux-setup-storage
sleep 3

# 2. 更新系統與安裝依賴
echo -e "${YELLOW}[2/5] 正在安裝系統依賴 (Python, yt-dlp, ffmpeg, zip, ttyd)...${NC}"
pkg update -y && pkg upgrade -y
pkg install python ffmpeg zip ttyd openssh curl wget -y

# 3. 安裝 Python 套件 (避開 pip upgrade 限制)
echo -e "${YELLOW}[3/5] 正在安裝 Python 核心套件 (Flask, CORS, yt-dlp)...${NC}"
# 注意：在 Termux 中不要執行 pip install --upgrade pip，這會導致報錯
pip install flask flask-cors yt-dlp

# 4. 安裝 LocalXpose (用於固定網址)
echo -e "${YELLOW}[4/5] 正在安裝 LocalXpose (固定網址工具)...${NC}"
if [ ! -f "$PREFIX/bin/loclx" ]; then
    ARCH=$(uname -m)
    if [ "$ARCH" == "aarch64" ]; then
        wget https://api.localxpose.io/api/v2/client/download/linux-arm64 -O loclx.zip
    else
        wget https://api.localxpose.io/api/v2/client/download/linux-arm -O loclx.zip
    fi
    unzip loclx.zip
    chmod +x loclx
    mv loclx $PREFIX/bin/
    rm loclx.zip
    echo -e "${GREEN}✅ LocalXpose 安裝成功！${NC}"
else
    echo -e "${GREEN}✅ LocalXpose 已存在，跳過安裝。${NC}"
fi

# 5. 建立下載目錄與啟動
echo -e "${YELLOW}[5/5] 正在建立下載目錄並啟動伺服器...${NC}"
mkdir -p /sdcard/Download/temp

echo -e "${GREEN}✅ 部署完成！${NC}"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${YELLOW}🔑 如何設定固定網址：${NC}"
echo -e "1. 前往 https://localxpose.io 註冊免費帳號"
echo -e "2. 在 Termux 執行: ${GREEN}loclx account login${NC}"
echo -e "3. 啟動固定網址轉發 (下載伺服器):"
echo -e "   ${GREEN}loclx tunnel http --to 127.0.0.1:5000 --subdomain 您的名稱${NC}"
echo -e "4. 啟動固定網址轉發 (控制台):"
echo -e "   ${GREEN}loclx tunnel http --to 127.0.0.1:8080 --subdomain 您的名稱-term${NC}"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${GREEN}💡 啟動指令：${NC}"
echo -e "   python server.py"
echo -e "   ttyd -p 8080 bash"
echo -e "${BLUE}------------------------------------------${NC}"

# 自動啟動 server.py
python server.py
