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

def inspect():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        
        print("Navegando a Tableau...")
        page.goto(TABLEAU_URL, timeout=45000)
        
        try:
            page.wait_for_selector("input[name='username']", timeout=10000)
            print("Login...")
            page.fill("input[name='username']", USER)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_selector("input[name='username']", state="detached", timeout=30000)
            print("Logged in!")
        except Exception as e:
            print("Already logged in or no form:", e)
            
        print("Esperando 25s...")
        time.sleep(25)
        
        page.screenshot(path="scratch_tableau_initial.png")
        print("Screenshot guardado en scratch_tableau_initial.png")
        
        # Guardar HTML frames info
        frames = page.frames
        print(f"Total frames: {len(frames)}")
        for idx, f in enumerate(frames):
            print(f"Frame {idx}: name='{f.name}', url='{f.url}'")
            
        # Buscar elementos en los frames
        for f in frames:
            try:
                checkboxes = f.locator("input[type='checkbox']").all()
                print(f"Frame {f.name} has {len(checkboxes)} checkbox inputs")
                spans = f.locator("span, div").filter(has_text="Status Recv").all()
                print(f"Frame {f.name} status recv elements: {len(spans)}")
            except Exception as ex:
                pass
                
        browser.close()

if __name__ == '__main__':
    inspect()
