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
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    
    print("Navigating to NIMS...")
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
        print("Logged in successfully!")
        
    print("Clicking 'Quản lý thuê bao'...")
    page.locator(
        "a:has-text('Quản lý thuê bao'), td:has-text('Quản lý thuê bao'), span:has-text('Quản lý thuê bao'), "
        "a:has-text('Subscriber Management'), td:has-text('Subscriber Management'), span:has-text('Subscriber Management')"
    ).first.click(force=True)
    time.sleep(3)
    
    print("--- DUMPING ALL VISIBLE TEXT IN PAGE AFTER CLICKING MENU ---")
    elements = page.locator("a, span, td, div").all()
    for idx, el in enumerate(elements):
        try:
            txt = el.inner_text().strip()
            if "Báo cáo" in txt or "báo cáo" in txt or "thông kê" in txt or "băng rộng" in txt:
                print(f"  Match [{idx}]: tag={el.evaluate('e=>e.tagName')}, class={el.evaluate('e=>e.className')}, text={repr(txt)}")
        except Exception:
            pass

    # Try clicking the report link
    submenu = page.locator("a:has-text('Báo cáo thuê bao băng rộng cố định'), span:has-text('Báo cáo thuê bao băng rộng cố định'), td:has-text('Báo cáo thuê bao băng rộng cố định')").first
    print(f"Submenu count: {submenu.count()}")
    
    if submenu.count() > 0:
        print("Clicking submenu option...")
        
        # Listen for new tab
        new_pages = []
        context.on("page", lambda p: new_pages.append(p))
        
        submenu.click(force=True)
        time.sleep(10)
        
        print(f"Total tabs opened: {len(context.pages)}")
        for idx, pg in enumerate(context.pages):
            print(f"  Tab [{idx}]: url={pg.url}")
            
        report_page = context.pages[-1]
        print(f"Report page title: {report_page.title()}")
        
        inputs = report_page.locator("input").all()
        print(f"Total inputs on report page: {len(inputs)}")
        for idx, inp in enumerate(inputs):
            print(f"  Input [{idx}]: id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, value={repr(inp.get_attribute('value'))}")
            
    browser.close()
