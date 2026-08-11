import os
import sys
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

USER = os.getenv("TABLEAU_USER", "vtp_branch")
PASSWORD = os.getenv("TABLEAU_PASSWORD", "B1t3l@123")
TABLEAU_URL = os.getenv("TABLEAU_URL", "http://10.121.43.82/#/views/FBB_Monitoring/GNOCWOPending_1")

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    page.set_viewport_size({"width": 1920, "height": 1080})
    
    print(f"Navigating to {TABLEAU_URL}...")
    page.goto(TABLEAU_URL, timeout=45000)
    
    try:
        page.wait_for_selector("input[name='username']", timeout=10000)
        page.fill("input[name='username']", USER)
        page.fill("input[name='password']", PASSWORD)
        page.click("button[type='submit']")
        page.wait_for_selector("input[name='username']", state="detached", timeout=30000)
    except Exception as e:
        print(f"Login skip/ok: {e}")
        
    time.sleep(15)
    frame = page.frame_locator("iframe").first
    dl_btn = frame.locator("button#download, [data-tb-test-id='download-Export-Button']").first
    print("Clicking download button...")
    dl_btn.click(force=True)
    time.sleep(4)
    
    page.screenshot(path="tableau_popup.png")
    
    # Print text of all buttons and menu items in frame
    print("--- ALL BUTTONS IN FRAME ---")
    btns = frame.locator("button, span, div[role='button'], div[role='menuitem']").all()
    for b in btns:
        try:
            txt = b.inner_text().strip()
            if txt and len(txt) < 50:
                print(f"  Frame Item: tag={b.evaluate('el => el.tagName')}, text={repr(txt)}")
        except Exception:
            pass
            
    print("--- ALL BUTTONS IN PAGE ---")
    btns_p = page.locator("button, span, div[role='button'], div[role='menuitem']").all()
    for b in btns_p:
        try:
            txt = b.inner_text().strip()
            if txt and len(txt) < 50:
                print(f"  Page Item: tag={b.evaluate('el => el.tagName')}, text={repr(txt)}")
        except Exception:
            pass

    browser.close()
