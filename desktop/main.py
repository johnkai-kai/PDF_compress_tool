"""
main.py — PDF Compressor 桌面版進入點
"""
import sys
from pathlib import Path

# 確保 desktop/ 目錄在 import 路徑中（支援直接執行與 PyInstaller 打包）
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    # 高 DPI 縮放（Windows 11）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PDF Compressor")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("johnkai-kai")

    # 應用程式圖示
    icon_path = Path(__file__).parent / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
