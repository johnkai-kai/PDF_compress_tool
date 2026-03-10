@echo off
:: PDF Compressor — 本地 Web 版啟動器
:: 啟動後自動開啟瀏覽器

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安裝
    pause
    exit /b 1
)

echo [INFO] 啟動本地 Web 伺服器 http://localhost:8080
echo [INFO] 按 Ctrl+C 停止

start "" http://localhost:8080
cd web
python -m http.server 8080
