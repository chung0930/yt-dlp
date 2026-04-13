#!/bin/bash

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🚀 Termux yt-dlp 遠端控制中心 v3.5 Final${NC}"
echo -e "${GREEN}✨ 終極穩定版 (Cloudflare Tunnel + Stable-Fix)${NC}"
echo -e "${BLUE}========================================${NC}"

# 1. 要求儲存權限
echo -e "${YELLOW}[1/5] 正在要求儲存權限，請在手機彈窗點擊「允許」...${NC}"
termux-setup-storage
sleep 3

# 2. 更新系統與安裝基礎依賴
echo -e "${YELLOW}[2/5] 正在更新系統並安裝基礎依賴 (Python, ffmpeg, zip, ttyd)...${NC}"
pkg update -y && pkg upgrade -y
pkg install python ffmpeg zip ttyd openssh curl wget -y

# 3. 安裝 Python 套件
echo -e "${YELLOW}[3/5] 正在安裝 Python 核心套件 (Flask, CORS, yt-dlp)...${NC}"
pip install flask flask-cors yt-dlp

# 4. 安裝 Cloudflared (最穩定的固定網址方案)
echo -e "${YELLOW}[4/5] 正在安裝 Cloudflared (透過 tur-repo 官方庫)...${NC}"
# 先安裝 tur-repo 官方擴充庫，確保能裝到 cloudflared
pkg install tur-repo -y
pkg update -y
pkg install cloudflared -y

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Cloudflared 安裝成功！${NC}"
else
    echo -e "${RED}❌ Cloudflared 安裝失敗，請嘗試手動執行: pkg install cloudflared${NC}"
fi

# 5. 建立下載目錄與啟動
echo -e "${YELLOW}[5/5] 正在建立下載目錄並啟動伺服器...${NC}"
mkdir -p /sdcard/Download/temp

echo -e "${GREEN}✅ 部署完成！${NC}"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${YELLOW}🔑 如何設定固定網址 (Cloudflare Tunnel)：${NC}"
echo -e "1. 啟動轉發 (下載伺服器):"
echo -e "   ${GREEN}cloudflared tunnel --url http://localhost:5000${NC}"
echo -e "2. 啟動轉發 (控制台):"
echo -e "   ${GREEN}cloudflared tunnel --url http://localhost:8080${NC}"
echo -e "   (執行後請記下畫面顯示的 .trycloudflare.com 網址)"
echo -e "${BLUE}------------------------------------------${NC}"
echo -e "${GREEN}💡 啟動指令：${NC}"
echo -e "   python server.py"
echo -e "   ttyd -p 8080 bash"
echo -e "${BLUE}------------------------------------------${NC}"

# 自動啟動 server.py
python server.py
