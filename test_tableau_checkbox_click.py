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

def test_clicks():
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
        
        print("=== MÉTODOS PARA MARCAR 'Processing' ===")
        
        # Método A: Buscar la etiqueta span/div que dice 'Processing' y hacerle click normal
        target_text = frame.locator("span:text-is('Processing')").first
        if target_text.count() > 0:
            print("Intento A: Clic en span:text-is('Processing')...")
            target_text.click()
            time.sleep(4)
            
        proc_cb = frame.locator("input[name*='Calculation_1551771557234716675'][name$='_1']").first
        print(f"Estado tras Intento A: checked={proc_cb.is_checked()}")
        
        if not proc_cb.is_checked():
            # Método B: Clic en el parent del input
            print("Intento B: Clic en parent del input de Processing...")
            parent = proc_cb.locator("xpath=..")
            parent.click()
            time.sleep(4)
            print(f"Estado tras Intento B: checked={proc_cb.is_checked()}")

        if not proc_cb.is_checked():
            # Método C: usar check() directo en el input
            print("Intento C: proc_cb.check(force=True)...")
            proc_cb.check(force=True)
            time.sleep(4)
            print(f"Estado tras Intento C: checked={proc_cb.is_checked()}")

        browser.close()

if __name__ == '__main__':
    test_clicks()
