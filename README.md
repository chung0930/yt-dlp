# Termux yt-dlp 終極下載器部署指南

## 1. 專案總覽

本專案旨在提供一個基於 **Termux** (作為後端伺服器) 和 **GitHub Pages** (作為前端介面) 的 YouTube/YouTube Music 下載解決方案。使用者可以透過美觀的前端介面提交下載請求，後端則負責執行實際的影音下載、處理、壓縮，並將結果回傳至前端供使用者下載。此系統支援多種下載模式，並以「一鍵部署」為目標，簡化設定流程。

## 2. 功能特色

*   **五種下載模式**：
    1.  YouTube Music 專輯下載：自動分資料夾，嵌入 1:1 裁剪的專輯封面，並包含音樂名稱、作曲人、專輯、發行日期等 metadata。
    2.  YouTube Music 單曲下載：嵌入 1:1 裁剪的專輯封面，並包含音樂名稱、作曲人、專輯、發行日期等 metadata。
    3.  YouTube Music 播放清單下載：將整個播放清單視為一張專輯，所有歌曲儲存於同一資料夾，嵌入封面，並包含 metadata。
    4.  YouTube 影片 1080p 下載：下載最佳 1080p 影片流和最佳音訊流，使用 `ffmpeg` 合併音軌與畫面。
    5.  YouTube 影片播放清單下載：同上，但為多個影片。
*   **自動依賴安裝**：後端部署腳本會自動安裝 `yt-dlp`, `ffmpeg`, `pigz`, `flask` 等必要工具。
*   **進度顯示**：前端介面會即時顯示下載進度、速度和預計剩餘時間。
*   **檔案處理**：
    *   單一檔案 (單音樂/單影片) 直接提供下載連結。
    *   多個檔案 (專輯/播放清單，超過三首歌曲或影片) 會使用 `pigz` 高效壓縮成 `.tar.gz` 檔案後提供下載。
*   **美觀前端 UI**：基於 Bootstrap 框架，提供直觀且響應式的操作介面。
*   **登入驗證**：前端提供簡易的客戶端登入介面，支援預設用戶管理。
*   **一鍵部署**：提供一個 `deploy.sh` 腳本，簡化 Termux 後端的設定與啟動。

## 3. 系統架構

*   **後端 (Termux)**：
    *   **核心程式**：`server.py` (Python Flask 應用)
    *   **主要工具**：`yt-dlp`, `ffmpeg`, `pigz`
    *   **網路穿透**：透過 `serveo.net` 建立 SSH 隧道，使本地伺服器可從外部網路存取。
*   **前端 (GitHub Pages)**：
    *   **靜態網頁**：`index.html` (包含 HTML, CSS, JavaScript)
    *   **用戶設定**：`users.js` (儲存登入憑證)

## 4. 部署指南

### 4.1. Termux 後端設定

1.  **安裝 Termux**：
    *   從 [F-Droid](https://f-droid.org/packages/com.termux/) 或 [GitHub Releases](https://github.com/termux/termux-app/releases) 下載並安裝最新版的 Termux 應用程式。**請勿從 Google Play 安裝，因為其版本已過時。**
2.  **下載後端檔案**：
    *   將 `server.py` 和 `deploy.sh` 這兩個檔案下載到您的手機儲存空間中，例如 `/sdcard/Download`。
3.  **開啟 Termux 並執行部署腳本**：
    *   開啟 Termux 應用程式。
    *   導航到您存放檔案的目錄：`cd /sdcard/Download` (如果您的檔案儲存在其他位置，請修改路徑)。
    *   給予 `deploy.sh` 執行權限：`chmod +x deploy.sh`
    *   執行部署腳本：`./deploy.sh`
    *   腳本會引導您完成以下步驟：
        *   請求儲存空間權限 (請務必允許)。
        *   更新系統並安裝 `python`, `ffmpeg`, `pigz`, `openssh` 等必要套件。
        *   安裝 Python 依賴 (`yt-dlp`, `flask`, `flask-cors`)。
        *   建立下載目錄 `/sdcard/Download` 和暫存目錄 `/sdcard/Download/temp`。
        *   啟動 `server.py` (Flask 應用程式將監聽 5000 埠)。
4.  **建立內網穿透 (Serveo.net)**：
    *   在 `server.py` 成功啟動後，**開啟另一個 Termux 視窗** (從通知欄下拉，點擊 `New session`)。
    *   在新視窗中執行以下命令：
        ```bash
        ssh -R 80:localhost:5000 serveo.net
        ```
    *   執行成功後，`serveo.net` 會提供一個類似 `https://random-string.serveo.net` 的公開 URL。**請記下這個 URL，稍後會用於前端設定。**
    *   **注意**：`serveo.net` 服務可能不穩定或有使用限制。如果遇到問題，可以嘗試其他內網穿透服務，例如 `ngrok` (需要註冊帳號)。

### 4.2. GitHub Pages 前端設定

1.  **建立 GitHub 倉庫**：
    *   在 GitHub 上建立一個新的公開 (Public) 倉庫，例如 `my-yt-downloader`。
2.  **上傳前端檔案**：
    *   將 `index.html` 和 `users.js` 這兩個檔案上傳到您剛建立的 GitHub 倉庫的根目錄。
3.  **啟用 GitHub Pages**：
    *   進入您的 GitHub 倉庫設定 (Settings)。
    *   點擊左側選單的 `Pages`。
    *   在 `Build and deployment` -> `Source` 中選擇 `Deploy from a branch`。
    *   在 `Branch` 中選擇 `main` (或您上傳檔案的分支)，並選擇 `/ (root)` 資料夾，然後點擊 `Save`。
    *   等待幾分鐘，GitHub Pages 會為您的網站生成一個公開 URL，例如 `https://your-github-username.github.io/my-yt-downloader/`。
4.  **更新前端伺服器 URL**：
    *   編輯您 GitHub 倉庫中的 `index.html` 檔案。
    *   找到 `<input type="text" id="server-url" class="form-control" placeholder="例如: https://xxxx.serveo.net">` 這一行。
    *   將 `value` 屬性設定為您在步驟 4.1.4 中獲取的 `serveo.net` 公開 URL。例如：
        ```html
        <input type="text" id="server-url" class="form-control" value="https://your-serveo-url.serveo.net">
        ```
    *   或者，您也可以在前端頁面載入後手動輸入此 URL。

## 5. 使用方式

1.  **開啟前端網頁**：在瀏覽器中開啟您的 GitHub Pages 網站 URL (例如 `https://your-github-username.github.io/my-yt-downloader/`)。
2.  **登入**：使用 `users.js` 中定義的用戶名和密碼登入。預設管理員帳號為 `admin`，密碼為 `password123`。您可以自行修改 `users.js` 來新增或修改用戶。
3.  **輸入連結與選擇模式**：在前端介面中，貼上 YouTube 或 YouTube Music 的連結，並選擇您想要的下載模式。
4.  **開始下載**：點擊「開始下載」按鈕。前端會顯示下載進度。
5.  **下載檔案**：下載完成後，會出現一個「下載完成！點擊取得檔案」的按鈕，點擊即可下載處理好的影音檔案或壓縮包。

## 6. 安全考量

*   **前端登入**：`users.js` 檔案是公開的，所有登入驗證都在客戶端進行。這意味著它不提供嚴格的安全性，僅用於基本的存取控制。**請勿在 `users.js` 中儲存任何敏感資訊。**
*   **後端公開 URL**：`serveo.net` 提供的 URL 是公開的，任何知道此 URL 的人都可以向您的 Termux 後端發送請求。雖然 `server.py` 中可以加入簡單的 token 驗證，但目前版本未實作。建議在不使用時關閉 Termux 中的 `server.py` 進程和 `serveo.net` 隧道。

## 7. 檔案列表

*   `server.py`: Termux 後端核心程式。
*   `deploy.sh`: Termux 後端一鍵部署腳本。
*   `index.html`: GitHub Pages 前端介面 (包含 HTML, CSS, JavaScript)。
*   `users.js`: 前端登入用戶設定檔。
*   `README.md`: 本部署指南。
*   `system_architecture.md`: 系統架構設計文件。

--- 

**作者**: Manus AI
**日期**: 2026年4月12日
