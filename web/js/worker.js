/**
 * worker.js — Ghostscript WASM Web Worker
 * 在背景執行緒執行 PDF 壓縮，避免 UI 凍結。
 *
 * Message Protocol:
 *   Incoming: { id, fileBuffer: ArrayBuffer, filename: string, quality: string }
 *   Outgoing (success): { id, success: true, data: Uint8Array, origSize: number, compSize: number }
 *   Outgoing (error):   { id, success: false, error: string }
 *   Outgoing (status):  { type: 'status', message: string }
 */

import { buildGsArgs } from './compressor.js';

// ─── Ghostscript WASM CDN ─────────────────────────────────────────────────
// 使用 jsdelivr CDN 載入 @jspawn/ghostscript-wasm
const GS_CDN_BASE = 'https://cdn.jsdelivr.net/npm/@jspawn/ghostscript-wasm@0.0.2/';
const GS_MODULE_URL = GS_CDN_BASE + 'gs.mjs';

// ─── 單例 Module 快取 ─────────────────────────────────────────────────────
let gsInstance = null;
let gsLoading = null;

/**
 * 初始化 Ghostscript WASM 模組（首次呼叫時載入，後續複用）
 */
async function initGhostscript() {
  if (gsInstance) return gsInstance;
  if (gsLoading) return gsLoading;

  postStatus('正在載入 Ghostscript WASM（約 18MB，首次需要時間）...');

  gsLoading = (async () => {
    // 動態 import ESM 模組
    const { default: createModule } = await import(GS_MODULE_URL);

    // 建立 Emscripten 模組實例
    const module = await createModule({
      locateFile: (filename) => {
        // 確保 WASM 二進位也從 CDN 載入
        return GS_CDN_BASE + filename;
      },
      // 靜默 Ghostscript 的 stdout/stderr（避免 Worker console 汙染）
      print: () => {},
      printErr: () => {},
    });

    postStatus('Ghostscript 已就緒');
    gsInstance = module;
    gsLoading = null;
    return module;
  })();

  return gsLoading;
}

// ─── 訊息處理 ─────────────────────────────────────────────────────────────
self.onmessage = async (event) => {
  const { id, fileBuffer, filename, quality } = event.data;

  try {
    const gs = await initGhostscript();

    const inputPath  = `/input_${id}.pdf`;
    const outputPath = `/output_${id}.pdf`;

    // 寫入輸入檔案至 WASM 虛擬 FS
    const inputData = new Uint8Array(fileBuffer);
    gs.FS.writeFile(inputPath, inputData);

    // 建立 Ghostscript 參數並執行
    const args = buildGsArgs(quality, inputPath, outputPath);

    let exitCode;
    try {
      exitCode = gs.callMain(args);
    } catch (e) {
      // Ghostscript 有時用 throw 回傳非零 exit code
      if (typeof e === 'number') {
        exitCode = e;
      } else {
        throw e;
      }
    }

    // 讀取輸出
    let compressedData;
    try {
      compressedData = gs.FS.readFile(outputPath);
    } catch {
      throw new Error(`Ghostscript 壓縮失敗（exit code ${exitCode}），可能是加密或損壞的 PDF`);
    }

    // 清理虛擬 FS
    try { gs.FS.unlink(inputPath); } catch {}
    try { gs.FS.unlink(outputPath); } catch {}

    // 驗證輸出是否為有效 PDF（前 4 bytes 應為 %PDF）
    if (compressedData.length < 4 ||
        compressedData[0] !== 0x25 || compressedData[1] !== 0x50 ||
        compressedData[2] !== 0x44 || compressedData[3] !== 0x46) {
      throw new Error('輸出不是有效的 PDF，壓縮可能失敗');
    }

    self.postMessage(
      {
        id,
        success: true,
        data: compressedData,
        origSize: fileBuffer.byteLength,
        compSize: compressedData.byteLength,
      },
      [compressedData.buffer]  // Transferable：避免複製大型 buffer
    );

  } catch (err) {
    // 清理：嘗試移除殘留的虛擬 FS 檔案
    try {
      const gs = gsInstance;
      if (gs) {
        try { gs.FS.unlink(`/input_${id}.pdf`);  } catch {}
        try { gs.FS.unlink(`/output_${id}.pdf`); } catch {}
      }
    } catch {}

    self.postMessage({ id, success: false, error: err.message ?? String(err) });
  }
};

// ─── 工具函式 ─────────────────────────────────────────────────────────────
function postStatus(message) {
  self.postMessage({ type: 'status', message });
}
