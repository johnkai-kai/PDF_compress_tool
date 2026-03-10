"""
compressor.py — Ghostscript subprocess 封裝
負責：
  - 尋找 Ghostscript 執行檔（捆綁版 / 系統安裝版）
  - 定義四種壓縮品質等級
  - 執行壓縮並回傳結果
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# ─── 品質等級定義 ────────────────────────────────────────────────────────
@dataclass
class QualityPreset:
    id: str
    label: str
    desc: str
    gs_flag: str
    extra_args: list[str]
    savings_min: float  # 預估節省（下限）
    savings_max: float  # 預估節省（上限）


QUALITY_PRESETS: dict[str, QualityPreset] = {
    "screen": QualityPreset(
        id="screen",
        label="低（螢幕）",
        desc="線上分享 · 最小體積",
        gs_flag="/screen",
        extra_args=[],
        savings_min=0.60,
        savings_max=0.80,
    ),
    "ebook": QualityPreset(
        id="ebook",
        label="中（電子書）",
        desc="電郵 · 平板閱讀",
        gs_flag="/ebook",
        extra_args=[],
        savings_min=0.40,
        savings_max=0.60,
    ),
    "printer": QualityPreset(
        id="printer",
        label="高（列印）",
        desc="辦公室列印品質",
        gs_flag="/printer",
        extra_args=[],
        savings_min=0.15,
        savings_max=0.35,
    ),
    "extreme": QualityPreset(
        id="extreme",
        label="極限（最小檔案）",
        desc="儲存空間嚴格受限",
        gs_flag="/screen",
        extra_args=[
            "-dColorImageDownsampleType=/Bicubic",
            "-dColorImageResolution=72",
            "-dGrayImageDownsampleType=/Bicubic",
            "-dGrayImageResolution=72",
            "-dMonoImageDownsampleType=/Bicubic",
            "-dMonoImageResolution=72",
            "-dOptimize=true",
            "-dEmbedAllFonts=false",
            "-dSubsetFonts=true",
            "-dCompressFonts=true",
        ],
        savings_min=0.75,
        savings_max=0.90,
    ),
}

DEFAULT_QUALITY = "ebook"


# ─── Ghostscript 執行檔路徑解析 ──────────────────────────────────────────
def find_ghostscript() -> str:
    """
    尋找 Ghostscript 執行檔。
    優先使用 PyInstaller 捆綁版，其次搜尋系統 PATH。
    找不到時拋出 FileNotFoundError。
    """
    # 1. PyInstaller 捆綁版（sys._MEIPASS）
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        for name in ("gswin64c.exe", "gswin32c.exe", "gs"):
            p = base / "gs_bin" / name
            if p.exists():
                return str(p)

    # 2. 系統 PATH（Windows / Unix）
    candidates = ["gswin64c", "gswin32c", "gs"]
    for cmd in candidates:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    raise FileNotFoundError(
        "找不到 Ghostscript！\n"
        "請安裝 Ghostscript 並確保它在系統 PATH 中。\n"
        "下載：https://www.ghostscript.com/releases/"
    )


# ─── 壓縮結果 ────────────────────────────────────────────────────────────
@dataclass
class CompressResult:
    input_path: Path
    output_path: Path
    orig_size: int
    comp_size: int
    success: bool
    error: str = ""

    @property
    def savings_pct(self) -> float:
        if not self.orig_size:
            return 0.0
        return (self.orig_size - self.comp_size) / self.orig_size * 100


# ─── 壓縮核心 ────────────────────────────────────────────────────────────
def compress_pdf(
    input_path: Path,
    output_path: Path,
    quality: str = DEFAULT_QUALITY,
    gs_executable: str | None = None,
) -> CompressResult:
    """
    使用 Ghostscript 壓縮單一 PDF。

    Parameters
    ----------
    input_path     : 來源 PDF 路徑
    output_path    : 輸出 PDF 路徑（會覆蓋已存在的檔案）
    quality        : 品質等級 ID（'screen'/'ebook'/'printer'/'extreme'）
    gs_executable  : Ghostscript 執行檔路徑；若 None，自動尋找

    Returns
    -------
    CompressResult
    """
    orig_size = input_path.stat().st_size

    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS[DEFAULT_QUALITY])
    gs = gs_executable or find_ghostscript()

    args = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dNOPAUSE",
        "-dBATCH",
        "-dSAFER",
        f"-dPDFSETTINGS={preset.gs_flag}",
        *preset.extra_args,
        f"-sOutputFile={output_path}",
        str(input_path),
    ]

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=120,  # 2 分鐘超時
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            raise RuntimeError(f"Ghostscript 錯誤（exit {result.returncode}）：{stderr[:300]}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Ghostscript 未產生輸出檔案")

        comp_size = output_path.stat().st_size
        return CompressResult(
            input_path=input_path,
            output_path=output_path,
            orig_size=orig_size,
            comp_size=comp_size,
            success=True,
        )

    except subprocess.TimeoutExpired:
        return CompressResult(
            input_path=input_path,
            output_path=output_path,
            orig_size=orig_size,
            comp_size=0,
            success=False,
            error="壓縮超時（超過 120 秒）",
        )
    except Exception as e:
        return CompressResult(
            input_path=input_path,
            output_path=output_path,
            orig_size=orig_size,
            comp_size=0,
            success=False,
            error=str(e),
        )
