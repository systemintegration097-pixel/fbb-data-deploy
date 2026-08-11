import os
import sys
import time
from playwright.sync_api import sync_playwright

NIMS_USER = "vtp_jose.mendoza"
NIMS_PASSWORD = "Fbb@05.2026"
NIMS_LOGIN_URL = "http://10.121.13.152:9009/NIMS/Index.do?request_locale=vi_VN"

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        ignore_https_errors=True,
        accept_downloads=True,
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    
    page.goto(NIMS_LOGIN_URL, timeout=45000)
    time.sleep(3)
    
    if page.locator("input#username").count() > 0:
        page.fill("input#username", NIMS_USER)
        page.fill("input#password", NIMS_PASSWORD)
        page.locator("input[type='submit'], button[type='submit']").first.click()
        page.wait_for_selector(
            "td:has-text('Quản lý'), td:has-text('Quản lý thuê bao'), "
            "span:has-text('Quản lý'), span:has-text('Quản lý thuê bao'), "
            "a:has-text('Quản lý'), a:has-text('Quản lý thuê bao'), "
            "td:has-text('Management'), td:has-text('Subscriber'), "
            "span:has-text('Management'), span:has-text('Subscriber'), "
            "a:has-text('Management'), a:has-text('Subscriber')",
            timeout=30000
        )
        
    page.locator(
        "a:has-text('Quản lý thuê bao'), td:has-text('Quản lý thuê bao'), span:has-text('Quản lý thuê bao'), "
        "a:has-text('Subscriber Management'), td:has-text('Subscriber Management'), span:has-text('Subscriber Management')"
    ).first.click(force=True)
    time.sleep(2)
    
    submenu = page.locator(
        "a:has-text('Báo cáo thuê bao băng rộng cố định'), td:has-text('Báo cáo thuê bao băng rộng cố định'), span:has-text('Báo cáo thuê bao băng rộng cố định'), "
        "a:has-text('Broadband Subscriber Report'), td:has-text('Broadband Subscriber Report'), span:has-text('Broadband Subscriber Report')"
    ).first
    submenu.click(force=True)
    time.sleep(5)
    
    frame = page.frame_locator("iframe[name='vt-bodyFrame']").first
    search_btn = frame.locator("button#btnSearch").first
    search_btn.wait_for(state="visible", timeout=30000)
    search_btn.click(force=True)
    time.sleep(12)
    
    export_btn = frame.locator("button:has-text('Export'), button[value='Export']").first
    
    with page.expect_download(timeout=120000) as download_info:
        export_btn.click(force=True)
        
    download = download_info.value
    import pathlib
    raw_content = pathlib.Path(download.path()).read_text(encoding="utf-8", errors="ignore")
    
    print("--- FIRST 2000 CHARACTERS OF DOWNLOADED CONTENT ---")
    print(repr(raw_content[:2000]))
    
    browser.close()
