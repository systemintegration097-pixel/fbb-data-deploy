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

def dump_filters():
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
        
        # Obtener todos los contenedores o elementos de filtro
        # Tableau usa divs con clases o atributos de aria para los quick filters
        print("--- DUMPING CHECKBOXES & LABELS ---")
        checkboxes = frame.locator("input[type='checkbox']").all()
        for idx, cb in enumerate(checkboxes):
            try:
                parent = cb.locator("xpath=..")
                parent_text = parent.inner_text()
                is_checked = cb.is_checked()
                name_attr = cb.get_attribute("name")
                id_attr = cb.get_attribute("id")
                aria_label = cb.get_attribute("aria-label")
                title = cb.get_attribute("title")
                print(f"CB #{idx}: checked={is_checked}, text='{parent_text.strip()}', name='{name_attr}', aria='{aria_label}', title='{title}'")
            except Exception as e:
                print(f"CB #{idx} error: {e}")
                
        print("\n--- DUMPING ALL FILTER TITLES AND SPANS ---")
        filter_headers = frame.locator("div.tab-aria-combobox, div[tabindex='0'], span.tab-title, div[aria-label]").all()
        for idx, fh in enumerate(filter_headers):
            try:
                text = fh.inner_text().strip()
                aria = fh.get_attribute("aria-label")
                role = fh.get_attribute("role")
                if text or aria:
                    print(f"Elem #{idx}: role='{role}', aria='{aria}', text='{text[:60]}'")
            except Exception:
                pass

        browser.close()

if __name__ == '__main__':
    dump_filters()
