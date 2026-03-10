/**
 * compressor.js — 壓縮品質預設值與工具函式
 * 負責定義 Ghostscript 參數、預估比例、格式化工具
 */

/** 壓縮品質等級定義 */
export const QUALITY_PRESETS = {
  screen: {
    id: 'screen',
    label: '低（螢幕）',
    desc: '線上分享、即時傳輸',
    gsFlag: '/screen',
    extraArgs: [],
    savingsMin: 0.60,
    savingsMid: 0.70,
    savingsMax: 0.80,
  },
  ebook: {
    id: 'ebook',
    label: '中（電子書）',
    desc: '電郵附件、平板閱讀',
    gsFlag: '/ebook',
    extraArgs: [],
    savingsMin: 0.40,
    savingsMid: 0.50,
    savingsMax: 0.60,
  },
  printer: {
    id: 'printer',
    label: '高（列印）',
    desc: '家用 / 辦公室列印',
    gsFlag: '/printer',
    extraArgs: [],
    savingsMin: 0.15,
    savingsMid: 0.25,
    savingsMax: 0.35,
  },
  extreme: {
    id: 'extreme',
    label: '極限（最小檔案）',
    desc: '儲存空間嚴格受限',
    gsFlag: '/screen',
    extraArgs: [
      '-dColorImageDownsampleType=/Bicubic',
      '-dColorImageResolution=72',
      '-dGrayImageDownsampleType=/Bicubic',
      '-dGrayImageResolution=72',
      '-dMonoImageDownsampleType=/Bicubic',
      '-dMonoImageResolution=72',
      '-dOptimize=true',
      '-dEmbedAllFonts=false',
      '-dSubsetFonts=true',
      '-dCompressFonts=true',
    ],
    savingsMin: 0.75,
    savingsMid: 0.82,
    savingsMax: 0.90,
  },
};

export const DEFAULT_QUALITY = 'ebook';

/**
 * 建立 Ghostscript 命令列參數
 * @param {string} quality  - 品質等級 ID
 * @param {string} inputPath  - WASM 虛擬 FS 輸入路徑
 * @param {string} outputPath - WASM 虛擬 FS 輸出路徑
 * @returns {string[]}
 */
export function buildGsArgs(quality, inputPath, outputPath) {
  const preset = QUALITY_PRESETS[quality] ?? QUALITY_PRESETS[DEFAULT_QUALITY];
  return [
    '-sDEVICE=pdfwrite',
    '-dNOPAUSE',
    '-dBATCH',
    '-dSAFER',
    `-dPDFSETTINGS=${preset.gsFlag}`,
    ...preset.extraArgs,
    `-sOutputFile=${outputPath}`,
    inputPath,
  ];
}

/**
 * 根據品質等級與原始大小估算壓縮後大小範圍
 * @param {number} origBytes
 * @param {string} quality
 * @returns {{ min: number, mid: number, max: number, savingsPct: string }}
 */
export function estimateSize(origBytes, quality) {
  const preset = QUALITY_PRESETS[quality] ?? QUALITY_PRESETS[DEFAULT_QUALITY];
  const min = Math.round(origBytes * (1 - preset.savingsMax));
  const mid = Math.round(origBytes * (1 - preset.savingsMid));
  const max = Math.round(origBytes * (1 - preset.savingsMin));
  const pctLow  = Math.round(preset.savingsMin * 100);
  const pctHigh = Math.round(preset.savingsMax * 100);
  return {
    min,
    mid,
    max,
    savingsPct: `${pctLow}–${pctHigh}%`,
    midFormatted: formatBytes(mid),
    rangeFormatted: `${formatBytes(min)} ~ ${formatBytes(max)}`,
  };
}

/**
 * 格式化位元組為人類可讀字串
 * @param {number} bytes
 * @returns {string}
 */
export function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

/**
 * 計算實際節省百分比
 * @param {number} origBytes
 * @param {number} compBytes
 * @returns {string}
 */
export function calcSavings(origBytes, compBytes) {
  if (!origBytes || origBytes === 0) return '0%';
  const pct = ((origBytes - compBytes) / origBytes) * 100;
  return `${pct.toFixed(1)}%`;
}
