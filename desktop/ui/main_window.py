"""
main_window.py — PyQt6 主視窗
Kilo Code 深色主題風格，支援拖放、批量壓縮、背景執行緒。
"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QMimeData, QUrl, QSize,
)
from PyQt6.QtGui import (
    QColor, QDragEnterEvent, QDropEvent, QFont, QPalette,
    QIcon,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QButtonGroup, QRadioButton, QGroupBox, QScrollArea,
    QListWidget, QListWidgetItem, QAbstractItemView,
)

from core.compressor import (
    QUALITY_PRESETS, DEFAULT_QUALITY,
    compress_pdf, find_ghostscript, CompressResult,
)
from core.file_manager import get_output_path, format_bytes, calc_savings_pct


# ─── 色彩常數 ─────────────────────────────────────────────────────────────
BG_PRIMARY   = "#1e1e1e"
BG_SECONDARY = "#252526"
BG_TERTIARY  = "#2d2d2d"
BORDER       = "#3e3e42"
ACCENT       = "#007acc"
SUCCESS      = "#4ec994"
WARN         = "#ce9178"
ERROR        = "#f48771"
TEXT_PRIMARY = "#d4d4d4"
TEXT_SEC     = "#858585"
TEXT_MONO    = "#9cdcfe"


STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "DM Sans", sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 16px;
    padding-top: 8px;
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_SEC};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: 4px;
    color: {TEXT_SEC};
}}
QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    padding: 6px 10px;
    border-radius: 4px;
}}
QRadioButton:hover {{ background-color: #37373d; }}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1.5px solid {BORDER};
    border-radius: 7px;
    background: {BG_TERTIARY};
}}
QRadioButton::indicator:checked {{
    border-color: {ACCENT};
    background: {ACCENT};
}}
QListWidget {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: none;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    color: {TEXT_PRIMARY};
}}
QListWidget::item {{
    padding: 6px 10px;
    border-radius: 4px;
}}
QListWidget::item:hover   {{ background-color: #37373d; }}
QListWidget::item:selected {{ background-color: #094771; color: white; }}
QTableWidget {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: rgba(62,62,66,0.5);
    font-size: 12px;
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    border: none;
}}
QTableWidget::item:selected {{ background: #094771; color: white; }}
QHeaderView::section {{
    background-color: {BG_TERTIARY};
    color: {TEXT_SEC};
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QProgressBar {{
    border: none;
    background: {BG_TERTIARY};
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}
QPushButton {{
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 7px 16px;
    border-radius: 4px;
    font-size: 13px;
}}
QPushButton:hover  {{ background-color: #37373d; border-color: {ACCENT}; }}
QPushButton:pressed {{ background-color: #1a3a5c; }}
QPushButton:disabled {{ opacity: 0.4; color: {TEXT_SEC}; }}
QPushButton#btn_primary {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton#btn_primary:hover   {{ background-color: #1a8ad4; }}
QPushButton#btn_primary:disabled {{ background-color: #3a3a4a; border-color: {BORDER}; color: {TEXT_SEC}; }}
QLineEdit {{
    background: {BG_TERTIARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 10px;
    color: {TEXT_MONO};
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLabel {{ color: {TEXT_PRIMARY}; }}
QLabel#label_sec  {{ color: {TEXT_SEC}; font-size: 11px; }}
QLabel#label_mono {{ color: {TEXT_MONO}; font-family: "Cascadia Code", monospace; font-size: 12px; }}
QLabel#stat_savings {{ color: {SUCCESS}; font-family: "Cascadia Code", monospace; font-size: 20px; font-weight: 500; }}
QScrollBar:vertical {{
    background: {BG_PRIMARY};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ─── 壓縮背景執行緒 ───────────────────────────────────────────────────────
class CompressWorker(QThread):
    progress = pyqtSignal(int, str, object)  # (index, filename, CompressResult | None)
    finished = pyqtSignal(list)              # list[CompressResult]
    error_msg = pyqtSignal(str)

    def __init__(self, file_list: list[Path], quality: str, output_dir: Path | None,
                 gs_path: str, parent=None):
        super().__init__(parent)
        self.file_list  = file_list
        self.quality    = quality
        self.output_dir = output_dir
        self.gs_path    = gs_path
        self._abort     = False

    def abort(self):
        self._abort = True

    def run(self):
        results = []
        for i, pdf_path in enumerate(self.file_list):
            if self._abort:
                break
            self.progress.emit(i, pdf_path.name, None)  # 開始
            out = get_output_path(pdf_path, self.output_dir)
            result = compress_pdf(pdf_path, out, self.quality, self.gs_path)
            results.append(result)
            self.progress.emit(i, pdf_path.name, result)  # 完成
        self.finished.emit(results)


# ─── 主視窗 ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Compressor")
        self.setMinimumSize(900, 620)
        self.resize(1000, 680)

        self.files: list[Path] = []
        self.results: list[CompressResult] = []
        self.output_dir: Path | None = None
        self.worker: CompressWorker | None = None

        # 找 Ghostscript
        try:
            self.gs_path = find_ghostscript()
        except FileNotFoundError as e:
            self.gs_path = ""
            # 初始化完成後再彈窗
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self._show_gs_error(str(e)))

        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_theme()
        self._update_all()

    # ─── UI 建構 ─────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = self._make_header()
        root.addWidget(header)

        # Body
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(12)

        # 上半：左面板（品質）+ 中（檔案列表）+ 右（統計）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._make_quality_panel())
        splitter.addWidget(self._make_file_panel())
        splitter.addWidget(self._make_stats_panel())
        splitter.setSizes([200, 420, 200])
        body_layout.addWidget(splitter, 1)

        # 輸出路徑列
        body_layout.addWidget(self._make_output_row())

        # 進度列
        self.progress_label = QLabel("就緒")
        self.progress_label.setObjectName("label_sec")
        body_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        body_layout.addWidget(self.progress_bar)

        # 操作按鈕列
        body_layout.addWidget(self._make_action_row())

        # 結果表格
        body_layout.addWidget(self._make_results_table(), 1)

        root.addWidget(body)

    def _make_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("header_bar")
        bar.setFixedHeight(46)
        bar.setStyleSheet(f"background:{BG_SECONDARY}; border-bottom:1px solid {BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)

        title = QLabel("⚙  PDF Compressor")
        title.setStyleSheet(f"font-weight:600; font-size:14px; color:{TEXT_PRIMARY};")
        badge = QLabel("v1.0.0")
        badge.setStyleSheet(f"font-family:'Cascadia Code',monospace; font-size:10px;"
                            f"color:{TEXT_SEC}; background:{BG_TERTIARY};"
                            f"border:1px solid {BORDER}; border-radius:3px; padding:1px 5px;")
        lay.addWidget(title)
        lay.addWidget(badge)
        lay.addStretch()

        gs_lbl = QLabel(f"Ghostscript: {'找到' if self.gs_path else '未找到'}")
        gs_lbl.setStyleSheet(f"font-size:11px; color:{'#4ec994' if self.gs_path else '#f48771'};")
        lay.addWidget(gs_lbl)
        return bar

    def _make_quality_panel(self) -> QWidget:
        box = QGroupBox("壓縮品質")
        lay = QVBoxLayout(box)
        lay.setSpacing(2)

        self.quality_radios: dict[str, QRadioButton] = {}
        for key, preset in QUALITY_PRESETS.items():
            rb = QRadioButton(f"{preset.label}\n{preset.desc}")
            rb.setChecked(key == DEFAULT_QUALITY)
            rb.setStyleSheet("QRadioButton { padding: 6px 8px; }")
            rb.toggled.connect(lambda checked, k=key: self._on_quality_changed(k) if checked else None)
            self.quality_radios[key] = rb
            lay.addWidget(rb)

        lay.addStretch()

        self.estimate_label = QLabel("預估節省 40–60%")
        self.estimate_label.setStyleSheet(
            f"background:{BG_TERTIARY}; border:1px solid {BORDER}; border-radius:4px;"
            f"padding:6px 8px; font-family:'Cascadia Code',monospace; font-size:12px; color:{SUCCESS};"
        )
        lay.addWidget(self.estimate_label)
        return box

    def _make_file_panel(self) -> QWidget:
        box = QGroupBox("待壓縮清單")
        lay = QVBoxLayout(box)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list_widget.setAcceptDrops(False)
        lay.addWidget(self.file_list_widget)

        btn_row = QHBoxLayout()
        self.file_count_label = QLabel("0 個檔案")
        self.file_count_label.setObjectName("label_sec")
        btn_row.addWidget(self.file_count_label)
        btn_row.addStretch()

        self.btn_add = QPushButton("+ 加入檔案")
        self.btn_add.clicked.connect(self._add_files_dialog)
        btn_row.addWidget(self.btn_add)

        self.btn_remove = QPushButton("移除選取")
        self.btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.btn_remove)

        self.btn_clear_list = QPushButton("清除全部")
        self.btn_clear_list.clicked.connect(self._clear_files)
        btn_row.addWidget(self.btn_clear_list)

        lay.addLayout(btn_row)
        return box

    def _make_stats_panel(self) -> QWidget:
        box = QGroupBox("大小對比")
        lay = QVBoxLayout(box)
        lay.setSpacing(10)

        def _stat_row(label_text: str, obj_name: str) -> QLabel:
            lbl = QLabel(label_text)
            lbl.setObjectName("label_sec")
            lay.addWidget(lbl)
            val = QLabel("—")
            val.setObjectName(obj_name)
            val.setStyleSheet(f"font-family:'Cascadia Code',monospace; font-size:16px; color:{TEXT_MONO};")
            lay.addWidget(val)
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color:{BORDER};")
            lay.addWidget(sep)
            return val

        self.stat_orig    = _stat_row("原始大小", "stat_orig")
        self.stat_comp    = _stat_row("壓縮後大小", "stat_comp")

        savings_lbl = QLabel("節省空間")
        savings_lbl.setObjectName("label_sec")
        lay.addWidget(savings_lbl)
        self.stat_savings = QLabel("—")
        self.stat_savings.setObjectName("stat_savings")
        lay.addWidget(self.stat_savings)

        lay.addStretch()

        note = QLabel("壓縮前顯示估算值\n壓縮後更新為實際數值\n全程本機執行，不上傳資料")
        note.setObjectName("label_sec")
        note.setWordWrap(True)
        lay.addWidget(note)
        return box

    def _make_output_row(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet(f"background:{BG_SECONDARY}; border:1px solid {BORDER}; border-radius:6px;")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 8, 12, 8)

        lbl = QLabel("輸出資料夾")
        lbl.setStyleSheet(f"color:{TEXT_SEC}; font-size:12px;")
        lay.addWidget(lbl)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("（預設：與原始 PDF 相同資料夾，檔名加 _compressed）")
        self.output_path_edit.setReadOnly(True)
        lay.addWidget(self.output_path_edit, 1)

        btn_browse = QPushButton("瀏覽…")
        btn_browse.setFixedWidth(64)
        btn_browse.clicked.connect(self._browse_output)
        lay.addWidget(btn_browse)

        btn_reset = QPushButton("重設")
        btn_reset.setFixedWidth(48)
        btn_reset.clicked.connect(self._reset_output)
        lay.addWidget(btn_reset)
        return row

    def _make_action_row(self) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)

        self.btn_compress = QPushButton("▶  開始壓縮")
        self.btn_compress.setObjectName("btn_primary")
        self.btn_compress.setFixedHeight(36)
        self.btn_compress.clicked.connect(self._start_compression)
        lay.addWidget(self.btn_compress)

        self.btn_open_output = QPushButton("開啟輸出資料夾")
        self.btn_open_output.clicked.connect(self._open_output_folder)
        self.btn_open_output.setEnabled(False)
        lay.addWidget(self.btn_open_output)

        lay.addStretch()
        return row

    def _make_results_table(self) -> QTableWidget:
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["檔案名稱", "原始大小", "壓縮後大小", "節省", "狀態"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            self.results_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        return self.results_table

    # ─── 主題 ────────────────────────────────────────────────────────────
    def _apply_theme(self):
        QApplication.instance().setStyleSheet(STYLESHEET)  # type: ignore

    # ─── 品質選擇 ────────────────────────────────────────────────────────
    def _current_quality(self) -> str:
        for key, rb in self.quality_radios.items():
            if rb.isChecked():
                return key
        return DEFAULT_QUALITY

    def _on_quality_changed(self, key: str):
        self._update_estimate()
        self._update_stats()

    def _update_estimate(self):
        quality = self._current_quality()
        preset = QUALITY_PRESETS[quality]
        lo = int(preset.savings_min * 100)
        hi = int(preset.savings_max * 100)
        self.estimate_label.setText(f"預估節省 {lo}–{hi}%")

    # ─── 檔案管理 ────────────────────────────────────────────────────────
    def _add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "選擇 PDF 檔案", "", "PDF Files (*.pdf)"
        )
        self._add_file_paths([Path(p) for p in paths])

    def _add_file_paths(self, paths: list[Path]):
        added = 0
        for p in paths:
            if p.suffix.lower() == ".pdf" and p not in self.files:
                self.files.append(p)
                added += 1
        if added:
            self._refresh_file_list()
            self._update_all()

    def _remove_selected(self):
        selected = {item.data(Qt.ItemDataRole.UserRole) for item in self.file_list_widget.selectedItems()}
        self.files = [f for f in self.files if f not in selected]
        self._refresh_file_list()
        self._update_all()

    def _clear_files(self):
        self.files.clear()
        self._refresh_file_list()
        self._update_all()

    def _refresh_file_list(self):
        self.file_list_widget.clear()
        for f in self.files:
            item = QListWidgetItem(f"{f.name}  ({format_bytes(f.stat().st_size)})")
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.file_list_widget.addItem(item)
        self.file_count_label.setText(f"{len(self.files)} 個檔案")

    # ─── 輸出路徑 ────────────────────────────────────────────────────────
    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if folder:
            self.output_dir = Path(folder)
            self.output_path_edit.setText(folder)

    def _reset_output(self):
        self.output_dir = None
        self.output_path_edit.clear()

    # ─── 壓縮 ────────────────────────────────────────────────────────────
    def _start_compression(self):
        if not self.files:
            QMessageBox.warning(self, "無檔案", "請先加入 PDF 檔案")
            return
        if not self.gs_path:
            QMessageBox.critical(self, "Ghostscript 未找到",
                                 "請安裝 Ghostscript 並重新啟動程式。\n"
                                 "下載：https://www.ghostscript.com/releases/")
            return

        self.btn_compress.setEnabled(False)
        self.results_table.setRowCount(0)
        self.results.clear()
        self.btn_open_output.setEnabled(False)
        total = len(self.files)
        self.progress_bar.setValue(0)

        # 預填結果表格
        self.results_table.setRowCount(total)
        for i, f in enumerate(self.files):
            self._set_table_row(i, f.name, format_bytes(f.stat().st_size), "—", "—", "待壓縮")

        self.worker = CompressWorker(
            list(self.files), self._current_quality(), self.output_dir, self.gs_path
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, idx: int, filename: str, result):
        total = len(self.files)
        if result is None:
            # 開始壓縮此檔案
            self.progress_label.setText(f"壓縮中 {filename} ({idx + 1}/{total})")
            self._set_table_row_status(idx, "壓縮中...")
        else:
            pct = int((idx + 1) / total * 100)
            self.progress_bar.setValue(pct)
            if result.success:
                savings = f"{result.savings_pct:.1f}%"
                self._set_table_row(idx, result.input_path.name,
                                    format_bytes(result.orig_size),
                                    format_bytes(result.comp_size),
                                    savings, "✓ 完成")
            else:
                self._set_table_row(idx, result.input_path.name,
                                    format_bytes(result.orig_size),
                                    "—", "—", f"✗ {result.error[:40]}")

    def _on_finished(self, results: list):
        self.results = results
        success = sum(1 for r in results if r.success)
        total   = len(results)
        self.progress_label.setText(f"完成！成功 {success}/{total}")
        self.progress_bar.setValue(100)
        self.btn_compress.setEnabled(True)
        self.btn_open_output.setEnabled(success > 0)
        self._update_stats()

    # ─── 結果表格工具 ────────────────────────────────────────────────────
    def _set_table_row(self, row, name, orig, comp, savings, status):
        mono_font = QFont("Cascadia Code, Consolas, monospace", 11)
        items = [
            (name,    TEXT_PRIMARY),
            (orig,    TEXT_MONO),
            (comp,    TEXT_MONO),
            (savings, SUCCESS if savings not in ("—", "0.0%") else TEXT_SEC),
            (status,  SUCCESS if status.startswith("✓") else (ERROR if status.startswith("✗") else TEXT_SEC)),
        ]
        for col, (text, color) in enumerate(items):
            cell = QTableWidgetItem(text)
            cell.setForeground(QColor(color))
            if col in (1, 2, 3):
                cell.setFont(mono_font)
            self.results_table.setItem(row, col, cell)

    def _set_table_row_status(self, row, status_text):
        item = self.results_table.item(row, 4)
        if item:
            item.setText(status_text)
            item.setForeground(QColor(ACCENT))

    # ─── 統計更新 ────────────────────────────────────────────────────────
    def _update_stats(self):
        total_orig = sum(f.stat().st_size for f in self.files)
        self.stat_orig.setText(format_bytes(total_orig) if total_orig else "—")

        done = [r for r in self.results if r.success]
        if done:
            total_comp = sum(r.comp_size for r in done)
            self.stat_comp.setText(format_bytes(total_comp))
            pct = calc_savings_pct(total_orig, total_comp)
            self.stat_savings.setText(f"{pct:.1f}%")
        elif self.files:
            preset = QUALITY_PRESETS[self._current_quality()]
            mid = 1 - (preset.savings_min + preset.savings_max) / 2
            est = int(total_orig * mid)
            self.stat_comp.setText(f"~{format_bytes(est)}")
            lo = int(preset.savings_min * 100)
            hi = int(preset.savings_max * 100)
            self.stat_savings.setText(f"{lo}–{hi}%")
        else:
            self.stat_comp.setText("—")
            self.stat_savings.setText("—")

    def _update_all(self):
        has_files = bool(self.files)
        self.btn_compress.setEnabled(has_files and bool(self.gs_path))
        self._update_estimate()
        self._update_stats()

    # ─── 開啟輸出資料夾 ───────────────────────────────────────────────────
    def _open_output_folder(self):
        folder = self.output_dir
        if not folder and self.results:
            folder = self.results[0].output_path.parent
        if folder and folder.exists():
            os.startfile(str(folder))

    # ─── 拖放支援 ────────────────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        pdfs  = [p for p in paths if p.suffix.lower() == ".pdf" and p.is_file()]
        if pdfs:
            self._add_file_paths(pdfs)
        else:
            from PyQt6.QtWidgets import QToolTip
            QToolTip.showText(event.position().toPoint(), "請拖放 PDF 檔案")

    # ─── Ghostscript 錯誤提示 ─────────────────────────────────────────────
    def _show_gs_error(self, msg: str):
        QMessageBox.warning(
            self, "Ghostscript 未找到",
            f"{msg}\n\n壓縮功能將無法使用。"
        )
