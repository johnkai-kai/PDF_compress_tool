"""
test_web_compress.py — Web 端 WASM 壓縮端到端驗證
使用 Playwright 模擬檔案上傳並驗證壓縮結果
"""
from playwright.sync_api import sync_playwright
import sys, time

ERRORS = []
PASSED = []

def check(cond, name):
    symbol = "[PASS]" if cond else "[FAIL]"
    print(f"  {symbol} {name}")
    (PASSED if cond else ERRORS).append(name)

PDF_PATH = r"C:\tmp\test_compress.pdf" if sys.platform == "win32" else "/tmp/test_compress.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    console_msgs = []
    page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: console_msgs.append(f"[pageerror] {err}"))

    print("\n── 1. 載入頁面 ──────────────────────────────────────")
    page.goto("http://localhost:8080", wait_until="networkidle")
    page.screenshot(path="/tmp/step1_loaded.png")
    check(page.locator("#drop-zone").is_visible(), "頁面載入成功")

    print("\n── 2. 上傳 PDF 檔案 ──────────────────────────────────")
    # 使用 file input 上傳
    page.locator("#file-input").set_input_files(PDF_PATH)
    page.wait_for_timeout(500)
    page.screenshot(path="/tmp/step2_file_added.png")

    file_count = page.locator("#file-count").text_content()
    print(f"  file-count: {file_count}")
    check("1" in file_count, f"檔案已加入清單（{file_count}）")

    # 壓縮按鈕應已啟用
    page.wait_for_timeout(300)
    btn_disabled = page.locator("#btn-compress").is_disabled()
    check(not btn_disabled, "壓縮按鈕已啟用")

    print("\n── 3. 確認大小估算 ───────────────────────────────────")
    stat_orig = page.locator("#stat-orig").text_content()
    stat_comp = page.locator("#stat-comp").text_content()
    print(f"  原始大小: {stat_orig}")
    print(f"  估算大小: {stat_comp}")
    check("—" not in stat_orig, f"原始大小已顯示：{stat_orig}")
    check("—" not in stat_comp, f"估算大小已顯示：{stat_comp}")

    print("\n── 4. 執行壓縮（等待 WASM 載入，最多 120 秒）────────")
    page.locator("#btn-compress").click()
    page.screenshot(path="/tmp/step3_compressing.png")

    # 等待壓縮完成（進度條到 100% 或 download 按鈕啟用）
    start = time.time()
    timeout_sec = 120
    done = False
    while time.time() - start < timeout_sec:
        try:
            # 檢查 download 按鈕是否啟用
            if not page.locator("#btn-download").is_disabled():
                done = True
                break
            # 或檢查進度狀態文字
            status = page.locator("#progress-status").text_content() or ""
            if "完成" in status:
                done = True
                break
        except Exception:
            pass
        page.wait_for_timeout(1000)
        elapsed = int(time.time() - start)
        if elapsed % 10 == 0:
            status = page.locator("#progress-status").text_content() or ""
            print(f"  ({elapsed}s) 狀態: {status}")

    page.screenshot(path="/tmp/step4_done.png")
    check(done, f"壓縮完成（{'成功' if done else '超時'}）")

    if done:
        print("\n── 5. 驗證壓縮結果 ───────────────────────────────────")
        stat_orig_after = page.locator("#stat-orig").text_content()
        stat_comp_after = page.locator("#stat-comp").text_content()
        stat_savings = page.locator("#stat-savings").text_content()
        print(f"  原始大小: {stat_orig_after}")
        print(f"  壓縮後大小: {stat_comp_after}")
        print(f"  節省: {stat_savings}")

        check("—" not in stat_comp_after, f"壓縮後大小已更新：{stat_comp_after}")
        check("%" in stat_savings, f"節省百分比已顯示：{stat_savings}")

        # 結果表格有一行
        result_rows = page.locator("#results-tbody tr").count()
        check(result_rows >= 1, f"結果表格有資料（{result_rows} 行）")

        # 狀態應顯示完成
        status_cell = page.locator("#results-tbody td").last.text_content() or ""
        print(f"  結果狀態欄: {status_cell}")

        print("\n── 6. 下載 ZIP ──────────────────────────────────────")
        with page.expect_download(timeout=10000) as dl_info:
            page.locator("#btn-download").click()
        download = dl_info.value
        print(f"  下載檔名: {download.suggested_filename}")
        check(download.suggested_filename.endswith(".pdf") or
              download.suggested_filename.endswith(".zip"),
              f"下載檔案格式正確：{download.suggested_filename}")

    print("\n── Console 訊息 ──────────────────────────────────────")
    errors_in_console = [m for m in console_msgs if "[error]" in m or "[pageerror]" in m]
    if errors_in_console:
        for e in errors_in_console[:5]:
            print(f"  ! {e[:120]}")
    else:
        print("  (無錯誤)")
    check(len(errors_in_console) == 0, "無 console 錯誤")

    browser.close()

print("\n=======================================================")
print(f"結果: PASS {len(PASSED)}/{len(PASSED)+len(ERRORS)}")
if ERRORS:
    print("FAIL:", ERRORS)
    sys.exit(1)
else:
    print("ALL PASS")
