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

def tree():
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
        
        print("=== TODAS LAS ETIQUETAS E INPUTS EN EL FRAME DE TABLEAU ===")
        # Encontrar todas las etiquetas con atributo 'name' o clase que contenga 'FI'
        inputs = frame.locator("input").all()
        for idx, inp in enumerate(inputs):
            name = inp.get_attribute("name") or ""
            tp = inp.get_attribute("type") or ""
            is_chk = inp.is_checked() if tp == "checkbox" else False
            # Obtener el contenedor div o span más cercano con texto
            parent_text = ""
            try:
                parent_text = inp.locator("xpath=ancestor::div[contains(@class, 'tab-widget') or contains(@class, 'FICheckRadio') or contains(@class, 'tab-aria')][1]").inner_text().replace('\n', ' ')
            except:
                pass
            print(f"Input #{idx}: type='{tp}', name='{name}', checked={is_chk}, parent_text='{parent_text[:80]}'")

        browser.close()

if __name__ == '__main__':
    tree()
