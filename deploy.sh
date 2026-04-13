#!/bin/bash

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🚀 Termux yt-dlp 遠端控制中心 v3.3 Final${NC}"
echo -e "${GREEN}✨ 終極穩定版 (ngrok + Stable-Fix)${NC}"
echo -e "${BLUE}========================================${NC}"

# 1. 要求儲存權限
echo -e "${YELLOW}[1/5] 正在要求儲存權限，請在手機彈窗點擊「允許」...${NC}"
termux-setup-storage
sleep 3

# 2. 更新系統與安裝基礎依賴
echo -e "${YELLOW}[2/5] 正在安裝系統依賴 (Python, ffmpeg, zip, ttyd)...${NC}"
pkg update -y && pkg upgrade -y
pkg install python ffmpeg zip ttyd openssh curl wget -y

# 3. 安裝 Python 套件
echo -e "${YELLOW}[3/5] 正在安裝 Python 核心套件 (Flask, CORS, yt-dlp)...${NC}"
# 注意：不更新 pip，直接安裝
pip install flask flask-cors yt-dlp

# 4. 安裝 ngrok (替代失效的 LocalXpose)
echo -e "${YELLOW}[4/5] 正在安裝 ngrok (固定網址穩定方案)...${NC}"
if [ ! -f "$PREFIX/bin/ngrok" ]; then
    pkg install tsu -y # 輔助工具
    pkg install ngrok -y
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}pkg 安裝失敗，嘗試手動下載 ngrok...${NC}"
        ARCH=$(uname -m)
        if [ "$ARCH" == "aarch64" ]; then
            wget https://bin.equinox.io/c/b34edq6jn9t/ngrok-v3-stable-linux-arm64.tgz -O ngrok.tgz
        else
            wget https://bin.equinox.io/c/b34edq6jn9t/ngrok-v3-stable-linux-arm.tgz -O ngrok.tgz
        }
        tar -xvzf ngrok.tgz
        chmod +x ngrok
        mv ngrok $PREFIX/bin/
        rm ngrok.tgz
    fi
    echo -e "${GREEN}✅ ngrok 安裝成功！${NC}"
else
    echo -e "${GREEN}✅ ngrok 已存在，跳過安裝。${NC}"
fi

# 5. 建立下載目錄與啟動
echo -e "${YELLOW}[5/5] 正在建立下載目錄並啟動伺服器...${NC}"
mkdir -p /sdcard/Download/temp

echo -e "${GREEN}✅ 部署完成！${NC}"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${YELLOW}🔑 如何設定固定網址 (ngrok)：${NC}"
echo -e "1. 前往 https://ngrok.com 註冊帳號並獲取 Authtoken"
echo -e "2. 在 Termux 執行: ${GREEN}ngrok config add-authtoken 您的TOKEN${NC}"
echo -e "3. 啟動轉發 (下載伺服器):"
echo -e "   ${GREEN}ngrok http 5000${NC}"
echo -e "4. 啟動轉發 (控制台):"
echo -e "   ${GREEN}ngrok http 8080${NC}"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${GREEN}💡 啟動指令：${NC}"
echo -e "   python server.py"
echo -e "   ttyd -p 8080 bash"
echo -e "${BLUE}------------------------------------------${NC}"

# 自動啟動 server.py
python server.py
