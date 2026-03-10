@echo off
:: PDF Compressor — 本地啟動器（需安裝 Python 3.10+ 與 PyQt6）
:: 如需安裝依賴：pip install -r desktop/requirements.txt

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安裝或不在 PATH 中
    echo 請至 https://python.org 下載安裝
    pause
    exit /b 1
)

:: 確認 PyQt6 已安裝
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo [INFO] 安裝依賴中...
    pip install -r desktop/requirements.txt
)

:: 確認 Ghostscript
gswin64c --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] 未在 PATH 中找到 Ghostscript
    echo 請至 https://www.ghostscript.com/releases/ 下載安裝
    echo 安裝後程式仍可開啟，但無法執行壓縮
)

python desktop/main.py
