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

def debug_filters():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(TABLEAU_URL, timeout=45000)
        
        try:
            page.wait_for_selector("input[name='username']", timeout=10000)
            page.fill("input[name='username']", USER)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_selector("input[name='username']", state="detached", timeout=30000)
        except Exception:
            pass
            
        time.sleep(25)
        frame = page.frame_locator("iframe").first
        
        print("=== ESTADO INICIAL DE CHECKBOXES WO STATUS Y STATUS RECV ===")
        cbs = frame.locator("input[type='checkbox']").all()
        for idx, cb in enumerate(cbs):
            try:
                txt = cb.locator("xpath=..").inner_text().strip()
                name = cb.get_attribute("name") or ""
                print(f"CB #{idx}: name='{name}', text='{txt}', checked={cb.is_checked()}")
            except Exception as e:
                pass
                
        # 1. Hacer clic en Status Recv RECOVERING
        print("\n--- Desmarcando RECOVERING ---")
        rec_cb = frame.locator("input[name*='STATUS_RECV'][name$='_1']").first
        if rec_cb.count() > 0:
            rec_cb.click(force=True)
            time.sleep(4)
            
        # 2. Hacer clic en Processing
        print("\n--- Marcando Processing ---")
        proc_cb = frame.locator("input[name*='Calculation_1551771557234716675'][name$='_1']").first
        if proc_cb.count() > 0:
            proc_cb.click(force=True)
            time.sleep(4)

        print("\n=== ESTADO TRAS CLICS DE CHECKBOXES ===")
        cbs = frame.locator("input[type='checkbox']").all()
        for idx, cb in enumerate(cbs):
            try:
                txt = cb.locator("xpath=..").inner_text().strip()
                name = cb.get_attribute("name") or ""
                print(f"CB #{idx}: name='{name}', text='{txt}', checked={cb.is_checked()}")
            except Exception as e:
                pass

        page.screenshot(path="scratch_tableau_after_clicks.png")
        print("\nScreenshot guardado en scratch_tableau_after_clicks.png")
        browser.close()

if __name__ == '__main__':
    debug_filters()
