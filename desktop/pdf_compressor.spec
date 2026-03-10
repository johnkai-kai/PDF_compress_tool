# pdf_compressor.spec — PyInstaller 打包規格
# 用法：pyinstaller desktop/pdf_compressor.spec
# 前提：gs_bin/ 目錄已存在（CI/CD workflow 自動下載）

import sys
from pathlib import Path

BASE = Path(SPECPATH)   # desktop/ 目錄

# Ghostscript 二進位路徑（由 CI/CD 下載至 desktop/gs_bin/）
GS_BIN = BASE / 'gs_bin'

block_cipher = None

a = Analysis(
    [str(BASE / 'main.py')],
    pathex=[str(BASE)],
    binaries=[
        # 將 gs_bin/ 下的所有檔案捆綁入 exe（gs_bin/ → _MEIPASS/gs_bin/）
        (str(GS_BIN / '*.exe'), 'gs_bin'),
        (str(GS_BIN / '*.dll'), 'gs_bin'),
    ] if GS_BIN.exists() else [],
    datas=[
        # 圖示
        (str(BASE / 'assets' / 'icon.ico'), 'assets'),
    ] if (BASE / 'assets' / 'icon.ico').exists() else [],
    hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PDF_Compressor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不顯示終端機視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE / 'assets' / 'icon.ico') if (BASE / 'assets' / 'icon.ico').exists() else None,
    uac_admin=False,
    version_file=None,
)
