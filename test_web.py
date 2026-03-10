"""
test_web.py — Web 端 Playwright 驗證腳本
"""
from playwright.sync_api import sync_playwright
import sys

ERRORS = []
PASSED = []

def check(cond, name):
    if cond:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        ERRORS.append(name)
        print(f"  [FAIL] {name}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: console_errors.append(str(err)))

    print("\n── 1. 頁面載入 ──────────────────────────────────────")
    page.goto("http://localhost:8080", wait_until="networkidle")
    page.screenshot(path="/tmp/web_initial.png", full_page=True)

    # 背景色應為深色
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    print(f"  body background: {bg}")
    check("30" in bg or "1e" in bg.lower() or "(30" in bg, "深色主題背景")

    print("\n── 2. 品質選擇器 ────────────────────────────────────")
    items = page.locator(".quality-item").all()
    check(len(items) == 4, f"4 個品質等級（實際：{len(items)}）")
    for item in items:
        label = item.locator(".quality-label").text_content()
        print(f"  → {label}")

    print("\n── 3. 拖放區域 ──────────────────────────────────────")
    drop_zone = page.locator("#drop-zone")
    check(drop_zone.is_visible(), "拖放區域可見")

    print("\n── 4. 壓縮按鈕初始狀態 ──────────────────────────────")
    btn = page.locator("#btn-compress")
    is_disabled = btn.is_disabled()
    print(f"  btn-compress disabled: {is_disabled}")
    check(is_disabled, "壓縮按鈕初始為 disabled")

    print("\n── 5. 統計區塊 ──────────────────────────────────────")
    check(page.locator("#stat-orig").is_visible(), "原始大小欄位可見")
    check(page.locator("#stat-comp").is_visible(), "壓縮後大小欄位可見")
    check(page.locator("#stat-savings").is_visible(), "節省比例欄位可見")

    print("\n── 6. 品質選擇互動 ──────────────────────────────────")
    # 點選「低（螢幕）」
    page.locator(".quality-item[data-quality='screen']").click()
    page.wait_for_timeout(200)
    estimate = page.locator("#estimate-value").text_content()
    print(f"  選 screen 後估算：{estimate}")
    check("60" in estimate and "80" in estimate, "screen 等級估算 60-80%")

    # 點選「極限」
    page.locator(".quality-item[data-quality='extreme']").click()
    page.wait_for_timeout(200)
    estimate = page.locator("#estimate-value").text_content()
    print(f"  選 extreme 後估算：{estimate}")
    check("75" in estimate, "extreme 等級估算包含 75%")

    print("\n── 7. Console 錯誤 ──────────────────────────────────")
    if console_errors:
        for e in console_errors:
            print(f"  ! {e}")
        check(False, f"無 console 錯誤（發現 {len(console_errors)} 個）")
    else:
        check(True, "無 console 錯誤")

    browser.close()

print("\n══════════════════════════════════════════════════════")
print(f"結果：通過 {len(PASSED)}/{len(PASSED)+len(ERRORS)} 項")
if ERRORS:
    print("失敗項目：", ERRORS)
    sys.exit(1)
else:
    print("全部通過！")
