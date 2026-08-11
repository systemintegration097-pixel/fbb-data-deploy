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

def test_toggles():
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
        
        # Encontrar el input de Processing en WO Status
        # En la lista de inputs, es la opción "Processing" de WO Status
        proc_input = None
        for inp in frame.locator("input[type='checkbox']").all():
            name = inp.get_attribute("name") or ""
            if "STATUS_RECV" not in name and name.endswith("_1") and "Calculation_5846" not in name:
                proc_input = inp
                break
                
        if not proc_input:
            print("No se encontró proc_input")
            browser.close()
            return

        print(f"proc_input encontrado: name='{proc_input.get_attribute('name')}', checked={proc_input.is_checked()}")
        
        # Probar Método 1: focus + Space
        print("\n--- Método 1: focus() + keyboard Space ---")
        proc_input.focus()
        page.keyboard.press("Space")
        time.sleep(3)
        print(f"Resultado Método 1: checked={proc_input.is_checked()}")

        # Probar Método 2: evaluate click
        if not proc_input.is_checked():
            print("\n--- Método 2: evaluate('el => el.click()') ---")
            proc_input.evaluate("el => el.click()")
            time.sleep(3)
            print(f"Resultado Método 2: checked={proc_input.is_checked()}")

        # Probar Método 3: dispatch_event click
        if not proc_input.is_checked():
            print("\n--- Método 3: dispatch_event('click') ---")
            proc_input.dispatch_event("click")
            time.sleep(3)
            print(f"Resultado Método 3: checked={proc_input.is_checked()}")

        # Probar Método 4: click en el parent span con text 'Processing' (usando XPath parent)
        if not proc_input.is_checked():
            print("\n--- Método 4: Clic en span relativo parent ---")
            parent_span = proc_input.locator("xpath=../..")
            parent_span.click(force=True)
            time.sleep(3)
            print(f"Resultado Método 4: checked={proc_input.is_checked()}")

        browser.close()

if __name__ == '__main__':
    test_toggles()
