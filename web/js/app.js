/**
 * app.js — 主 UI 控制器
 * 管理 DOM 事件、檔案狀態、Worker 通訊、JSZip 下載
 */

import {
  QUALITY_PRESETS,
  DEFAULT_QUALITY,
  estimateSize,
  formatBytes,
  calcSavings,
} from './compressor.js';

// ─── 全域狀態 ─────────────────────────────────────────────────────────────
const state = {
  files: [],           // { id, file, status, origSize, compSize, compData, error }
  quality: DEFAULT_QUALITY,
  isCompressing: false,
  worker: null,
  pendingCallbacks: {}, // id → { resolve, reject }
  nextId: 0,
};

// ─── DOM 參照 ─────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

let dom = {};

// ─── 初始化 ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  dom = {
    dropZone:        $('#drop-zone'),
    fileInput:       $('#file-input'),
    btnSelect:       $('#btn-select'),
    btnSelectMulti:  $('#btn-select-multi'),
    qualityItems:    $$('.quality-item'),
    estimateValue:   $('#estimate-value'),
    fileList:        $('#file-list'),
    fileListEmpty:   $('#file-list-empty'),
    fileCount:       $('#file-count'),
    btnClear:        $('#btn-clear'),
    statOrig:        $('#stat-orig'),
    statComp:        $('#stat-comp'),
    statSavings:     $('#stat-savings'),
    progressStatus:  $('#progress-status'),
    progressPct:     $('#progress-pct'),
    progressFill:    $('#progress-fill'),
    btnCompress:     $('#btn-compress'),
    btnDownload:     $('#btn-download'),
    resultsSection:  $('#results-section'),
    resultsTbody:    $('#results-tbody'),
    wasmLoading:     $('#wasm-loading'),
    wasmLoadingMsg:  $('#wasm-loading-msg'),
    toastContainer:  $('#toast-container'),
  };

  initWorker();
  bindEvents();
  updateQualityUI();
  updateStats();
  renderFileList();
});

// ─── Web Worker ───────────────────────────────────────────────────────────
function initWorker() {
  try {
    state.worker = new Worker('./js/worker.js', { type: 'module' });
    state.worker.onmessage = handleWorkerMessage;
    state.worker.onerror   = (e) => {
      console.error('Worker error:', e);
      showToast('Worker 初始化失敗：' + e.message, 'error');
    };
  } catch (e) {
    showToast('無法啟動壓縮 Worker：' + e.message, 'error');
  }
}

function handleWorkerMessage(event) {
  const msg = event.data;

  // 狀態訊息
  if (msg.type === 'status') {
    if (dom.wasmLoadingMsg) dom.wasmLoadingMsg.textContent = msg.message;
    return;
  }

  const cb = state.pendingCallbacks[msg.id];
  if (!cb) return;
  delete state.pendingCallbacks[msg.id];

  if (msg.success) {
    cb.resolve({ data: msg.data, origSize: msg.origSize, compSize: msg.compSize });
  } else {
    cb.reject(new Error(msg.error));
  }
}

function compressWithWorker(id, fileBuffer, filename, quality) {
  return new Promise((resolve, reject) => {
    state.pendingCallbacks[id] = { resolve, reject };
    state.worker.postMessage(
      { id, fileBuffer, filename, quality },
      [fileBuffer]  // Transferable
    );
  });
}

// ─── 事件綁定 ─────────────────────────────────────────────────────────────
function bindEvents() {
  // 檔案選擇
  dom.btnSelect.addEventListener('click', () => {
    dom.fileInput.removeAttribute('multiple');
    dom.fileInput.click();
  });
  dom.btnSelectMulti.addEventListener('click', () => {
    dom.fileInput.setAttribute('multiple', '');
    dom.fileInput.click();
  });
  dom.fileInput.addEventListener('change', (e) => {
    addFiles([...e.target.files]);
    e.target.value = '';
  });

  // 拖放
  dom.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dom.dropZone.classList.add('drag-over');
  });
  dom.dropZone.addEventListener('dragleave', () => {
    dom.dropZone.classList.remove('drag-over');
  });
  dom.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.dropZone.classList.remove('drag-over');
    const files = [...e.dataTransfer.files].filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
    if (files.length === 0) { showToast('請選擇 PDF 檔案', 'warn'); return; }
    addFiles(files);
  });

  // 品質選擇
  dom.qualityItems.forEach((item) => {
    item.addEventListener('click', () => {
      state.quality = item.dataset.quality;
      updateQualityUI();
      updateStats();
    });
  });

  // 清除清單
  dom.btnClear.addEventListener('click', () => {
    if (state.isCompressing) return;
    state.files = [];
    renderFileList();
    updateStats();
    clearResults();
  });

  // 開始壓縮
  dom.btnCompress.addEventListener('click', startCompression);

  // 下載 ZIP
  dom.btnDownload.addEventListener('click', downloadZip);
}

// ─── 檔案管理 ─────────────────────────────────────────────────────────────
function addFiles(files) {
  const pdfFiles = files.filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
  if (pdfFiles.length < files.length) {
    showToast(`已略過 ${files.length - pdfFiles.length} 個非 PDF 檔案`, 'warn');
  }
  pdfFiles.forEach((file) => {
    // 避免重複加入同名同大小檔案
    const exists = state.files.some((f) => f.file.name === file.name && f.file.size === file.size);
    if (!exists) {
      state.files.push({
        id: state.nextId++,
        file,
        status: 'pending',
        origSize: file.size,
        compSize: null,
        compData: null,
        error: null,
      });
    }
  });
  renderFileList();
  updateStats();
}

function removeFile(id) {
  state.files = state.files.filter((f) => f.id !== id);
  renderFileList();
  updateStats();
}

// ─── 壓縮主流程 ───────────────────────────────────────────────────────────
async function startCompression() {
  if (state.isCompressing || state.files.length === 0) return;

  state.isCompressing = true;
  dom.btnCompress.disabled = true;
  dom.btnDownload.disabled = true;
  clearResults();

  // 重置所有檔案狀態
  state.files.forEach((f) => {
    f.status  = 'pending';
    f.compSize = null;
    f.compData = null;
    f.error    = null;
  });

  // 顯示 WASM 載入中（首次）
  setProgressStatus('初始化中...', 0);

  const total = state.files.length;
  let done    = 0;
  let success = 0;

  for (const entry of state.files) {
    entry.status = 'compressing';
    renderFileList();
    updateResultsRow(entry);
    setProgressStatus(`壓縮中 ${entry.file.name}`, Math.round((done / total) * 100));

    try {
      // 顯示 WASM 載入 overlay（首次）
      if (done === 0) {
        dom.wasmLoading.classList.add('visible');
      }

      const arrayBuffer = await entry.file.arrayBuffer();
      const result = await compressWithWorker(entry.id, arrayBuffer, entry.file.name, state.quality);

      dom.wasmLoading.classList.remove('visible');

      entry.compSize = result.compSize;
      entry.compData = result.data;
      entry.status   = 'done';
      success++;
    } catch (err) {
      dom.wasmLoading.classList.remove('visible');
      entry.status = 'error';
      entry.error  = err.message;
      showToast(`${entry.file.name}：${err.message}`, 'error');
    }

    done++;
    renderFileList();
    updateResultsRow(entry);
    setProgressStatus(
      done < total ? `完成 ${done}/${total}` : `全部完成 (${success}/${total} 成功)`,
      Math.round((done / total) * 100)
    );
  }

  dom.progressFill.classList.add('done');
  dom.btnDownload.disabled = (success === 0);
  // 動態更新下載按鈕文字
  if (dom.btnDownload) {
    dom.btnDownload.innerHTML = success === 1
      ? `<svg viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M7.5 1v9M4 7l3.5 3.5L11 7" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M2 13h11" stroke-linecap="round"/></svg> 下載 PDF`
      : `<svg viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M7.5 1v9M4 7l3.5 3.5L11 7" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M2 13h11" stroke-linecap="round"/></svg> 下載 ZIP`;
  }
  state.isCompressing = false;
  dom.btnCompress.disabled = false;
  updateStats();

  if (success > 0) {
    const hint = success === 1 ? '按「下載 PDF」取得結果' : '按「下載 ZIP」取得全部結果';
    showToast(`壓縮完成！成功 ${success} 個檔案，${hint}`, 'success');
  }
}

// ─── 下載 ────────────────────────────────────────────────────────────────
async function downloadZip() {
  const done = state.files.filter((f) => f.status === 'done' && f.compData);
  if (done.length === 0) return;

  // 單一檔案：直接下載 PDF（不包 ZIP，確保 Adobe 可開啟）
  if (done.length === 1) {
    const entry = done[0];
    const outName = entry.file.name.replace(/\.pdf$/i, '_compressed.pdf');
    const blob = new Blob([entry.compData], { type: 'application/pdf' });
    _triggerDownload(blob, outName);
    return;
  }

  // 多個檔案：打包成 ZIP
  if (!window.JSZip) {
    showToast('JSZip 尚未載入，請重新整理頁面', 'error');
    return;
  }
  const zip = new window.JSZip();
  done.forEach((entry) => {
    zip.file(entry.file.name.replace(/\.pdf$/i, '_compressed.pdf'), entry.compData);
  });
  const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
  _triggerDownload(blob, 'compressed_pdfs.zip');
}

function _triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── UI 更新 ──────────────────────────────────────────────────────────────
function updateQualityUI() {
  dom.qualityItems.forEach((item) => {
    item.classList.toggle('active', item.dataset.quality === state.quality);
  });
  const preset = QUALITY_PRESETS[state.quality];
  if (dom.estimateValue) {
    dom.estimateValue.textContent = `預估節省 ${Math.round(preset.savingsMin * 100)}–${Math.round(preset.savingsMax * 100)}%`;
  }
}

function updateStats() {
  const totalOrig = state.files.reduce((s, f) => s + f.origSize, 0);
  const doneFiles = state.files.filter((f) => f.status === 'done' && f.compSize != null);
  const totalComp = doneFiles.reduce((s, f) => s + f.compSize, 0);

  if (dom.statOrig) dom.statOrig.textContent = formatBytes(totalOrig);

  if (doneFiles.length > 0) {
    // 顯示實際結果
    dom.statComp.textContent = formatBytes(totalComp);
    dom.statComp.className   = 'stat-value';
    dom.statSavings.textContent = calcSavings(totalOrig, totalComp);
  } else if (totalOrig > 0) {
    // 顯示估算
    const est = estimateSize(totalOrig, state.quality);
    dom.statComp.textContent = est.midFormatted;
    dom.statComp.className   = 'stat-value estimated';
    dom.statSavings.textContent = est.savingsPct;
  } else {
    dom.statComp.textContent = '—';
    dom.statComp.className   = 'stat-value';
    dom.statSavings.textContent = '—';
  }
}

function renderFileList() {
  if (!dom.fileList) return;
  dom.fileList.innerHTML = '';

  if (state.files.length === 0) {
    dom.fileListEmpty.style.display = 'block';
    dom.fileCount.textContent = '0 個檔案';
    return;
  }

  dom.fileListEmpty.style.display = 'none';
  dom.fileCount.textContent = `${state.files.length} 個檔案`;

  state.files.forEach((entry) => {
    const item = document.createElement('div');
    item.className = 'file-item';
    item.innerHTML = `
      <svg class="file-item-icon" viewBox="0 0 16 16" fill="currentColor">
        <path d="M4 0h5.5L14 4.5V16H4V0zm1 1v14h8V5h-4V1H5zm5 0v3.5h3.5L10 1z"/>
      </svg>
      <div class="file-item-info">
        <div class="file-item-name" title="${escHtml(entry.file.name)}">${escHtml(entry.file.name)}</div>
        <div class="file-item-size">${formatBytes(entry.origSize)}${entry.compSize != null ? ` → ${formatBytes(entry.compSize)}` : ''}</div>
      </div>
      <span class="file-item-status ${entry.status}">${statusLabel(entry)}</span>
      <button class="file-item-remove" data-id="${entry.id}" title="移除" ${state.isCompressing ? 'disabled' : ''}>
        <svg viewBox="0 0 12 12" fill="currentColor"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </button>
    `;
    dom.fileList.appendChild(item);
  });

  // 事件代理：移除按鈕
  dom.fileList.querySelectorAll('.file-item-remove').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const id = parseInt(e.currentTarget.dataset.id, 10);
      removeFile(id);
    });
  });
}

function statusLabel(entry) {
  switch (entry.status) {
    case 'pending':     return '待壓縮';
    case 'compressing': return '壓縮中...';
    case 'done':        return `✓ ${calcSavings(entry.origSize, entry.compSize)}`;
    case 'error':       return '✗ 失敗';
    default: return '';
  }
}

function setProgressStatus(msg, pct) {
  if (dom.progressStatus) dom.progressStatus.textContent = msg;
  if (dom.progressPct)    dom.progressPct.textContent    = `${pct}%`;
  if (dom.progressFill) {
    dom.progressFill.style.width = `${pct}%`;
    dom.progressFill.classList.remove('done', 'error');
  }
}

function clearResults() {
  if (dom.resultsTbody)  dom.resultsTbody.innerHTML = '';
  if (dom.progressFill) {
    dom.progressFill.style.width = '0%';
    dom.progressFill.classList.remove('done', 'error');
  }
  if (dom.progressStatus) dom.progressStatus.textContent = '就緒';
  if (dom.progressPct)    dom.progressPct.textContent    = '';
  if (dom.btnDownload)    dom.btnDownload.disabled = true;
}

function updateResultsRow(entry) {
  if (!dom.resultsTbody) return;
  let row = dom.resultsTbody.querySelector(`tr[data-id="${entry.id}"]`);
  if (!row) {
    row = document.createElement('tr');
    row.dataset.id = entry.id;
    dom.resultsTbody.appendChild(row);
  }

  const savings = entry.compSize != null ? calcSavings(entry.origSize, entry.compSize) : '—';
  const compStr = entry.compSize != null ? formatBytes(entry.compSize) : '—';

  let statusBadge;
  switch (entry.status) {
    case 'pending':     statusBadge = '<span class="status-badge pending">待壓縮</span>'; break;
    case 'compressing': statusBadge = '<span class="status-badge running">壓縮中</span>'; break;
    case 'done':        statusBadge = '<span class="status-badge done">✓ 完成</span>';   break;
    case 'error':       statusBadge = `<span class="status-badge error" title="${escHtml(entry.error ?? '')}">✗ 失敗</span>`; break;
    default: statusBadge = '';
  }

  row.innerHTML = `
    <td class="col-name" title="${escHtml(entry.file.name)}">${escHtml(entry.file.name)}</td>
    <td class="col-size">${formatBytes(entry.origSize)}</td>
    <td class="col-size">${compStr}</td>
    <td class="col-savings">${savings}</td>
    <td class="col-status">${statusBadge}</td>
  `;

  // 顯示結果區塊
  if (dom.resultsSection) dom.resultsSection.style.display = 'block';
}

// ─── Toast 通知 ───────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  if (!dom.toastContainer) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ─── 工具 ────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
