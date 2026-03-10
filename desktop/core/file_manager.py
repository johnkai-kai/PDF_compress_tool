"""file_manager.py — 輸出路徑管理"""
from pathlib import Path


def get_output_path(input_path: Path, output_dir: Path | None = None) -> Path:
    """
    計算壓縮輸出路徑。
    - 若 output_dir 未指定：輸出至與輸入相同目錄
    - 檔名格式：原始檔名_compressed.pdf
    """
    dir_ = output_dir if output_dir else input_path.parent
    return dir_ / f"{input_path.stem}_compressed{input_path.suffix}"


def format_bytes(size: int) -> str:
    """將位元組格式化為人類可讀字串"""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.2f} MB"


def calc_savings_pct(orig: int, comp: int) -> float:
    """計算節省百分比（0–100）"""
    if not orig:
        return 0.0
    return (orig - comp) / orig * 100
