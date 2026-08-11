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

def find_elements():
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
        
        print("=== BÚSQUEDA DINÁMICA DE ELEMENTOS DE FILTRO ===")
        # Probar selecciones por texto exacto en las opciones de filtro
        texts_to_check = ["Processing", "Wait_for_accept", "Closed", "RECOVERING", "Null"]
        
        for txt in texts_to_check:
            print(f"\nBusca text: '{txt}'")
            locs = frame.locator(f"span:text-is('{txt}'), div:text-is('{txt}'), label:has-text('{txt}')").all()
            print(f"  Encontrados {len(locs)} elementos.")
            for idx, l in enumerate(locs):
                try:
                    tag = l.evaluate("e => e.tagName")
                    cls = l.get_attribute("class") or ""
                    parent_tag = l.locator("xpath=..").evaluate("e => e.tagName")
                    cb_child = l.locator("xpath=..//input[@type='checkbox']").first
                    has_cb = cb_child.count() > 0
                    is_checked = cb_child.is_checked() if has_cb else "No CB"
                    print(f"    Elem #{idx}: tag='{tag}', class='{cls}', parent='{parent_tag}', has_cb={has_cb}, checked={is_checked}")
                except Exception as ex:
                    print(f"    Elem #{idx} error: {ex}")

        browser.close()

if __name__ == '__main__':
    find_elements()
