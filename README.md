# PDF Compressor

PDF 壓縮工具，支援 **Web 版**（GitHub Pages）與 **Windows 執行檔**兩種形式。

## 功能

- 四種壓縮品質等級：螢幕（最小）/ 電子書 / 列印 / 極限
- 批量壓縮多個 PDF
- 壓縮前顯示預估節省比例，壓縮後顯示實際對比
- 自訂輸出資料夾（預設：原始目錄，檔名加 `_compressed`）
- 全程本機執行，不上傳任何資料

---

## Web 版（GitHub Pages）

直接在瀏覽器使用，無需安裝：

**https://johnkai-kai.github.io/PDF_compress_tool/**

- 使用 Ghostscript WASM，壓縮引擎完全在瀏覽器本機執行
- 批量完成後可一鍵下載 ZIP

---

## Windows 執行檔

從 [Releases](https://github.com/johnkai-kai/PDF_compress_tool/releases) 下載 `PDF_Compressor.exe`

- 獨立執行檔，無需安裝 Python 或 Ghostscript
- 支援拖放 PDF 至視窗

---

## 本地開發

### Web 版

```bash
# 需用 HTTP server 啟動（直接開啟 file:// 無法載入 WASM）
cd web
python -m http.server 8080
# 瀏覽器開啟 http://localhost:8080
```

### Desktop 版

**前提：** 系統需安裝 [Ghostscript](https://www.ghostscript.com/releases/)

```bash
cd desktop
pip install -r requirements.txt
python main.py
```

### 打包 EXE（本地）

```bash
# 需先將 gswin64c.exe 等檔案放至 desktop/gs_bin/
cd desktop
pyinstaller pdf_compressor.spec
# 輸出：dist/PDF_Compressor.exe
```

---

## CI/CD

| 觸發條件 | 動作 |
|---------|------|
| push `main`（含 `web/**` 變更） | 自動部署至 GitHub Pages |
| push tag `v*.*.*` | 打包 Windows .exe 並建立 GitHub Release |

---

## 壓縮品質等級說明

| 等級 | Ghostscript 設定 | 預估節省 | 適用情境 |
|------|-----------------|---------|---------|
| 低（螢幕） | `/screen` 72 DPI | 60–80% | 線上分享 |
| 中（電子書） | `/ebook` 150 DPI | 40–60% | 電郵、平板 |
| 高（列印） | `/printer` 300 DPI | 15–35% | 辦公列印 |
| 極限（最小） | `/screen` + 強制 72 DPI | 75–90% | 嚴格受限 |
