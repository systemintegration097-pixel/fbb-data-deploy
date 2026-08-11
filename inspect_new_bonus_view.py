import os
import sys
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

USER = os.getenv("TABLEAU_USER", "vtp_branch")
PASSWORD = os.getenv("TABLEAU_PASSWORD", "B1t3l@123")
NEW_URL = "http://10.121.43.82/#/views/BonusCommistion/Detail_Data_Implementation?:iid=2"

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        print(f"Navegando a: {NEW_URL}")
        page.goto(NEW_URL, timeout=45000)
        try:
            page.wait_for_selector("input[name='username']", timeout=10000)
            print("Formulario de login detectado, autenticando...")
            page.fill("input[name='username']", USER)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_selector("input[name='username']", state="detached", timeout=30000)
        except Exception as e:
            print(f"No se detecto login (quizas ya autenticado): {e}")

        print("Esperando 25s renderizado...")
        time.sleep(25)
        page.screenshot(path="./scratch_new_bonus_view.png")

        frame = page.frame_locator("iframe").first

        print("\n=== Buscando tabla/headers ===")
        # Tableau suele renderizar celdas de tabla como divs con role gridcell o similar
        headers = frame.locator("[class*='tableau-tooltip'], [role='columnheader'], [class*='header']").all()
        print(f"Elementos header-like: {len(headers)}")

        print("\n=== Checkboxes de filtros disponibles ===")
        cbs = frame.locator("input[type='checkbox']").all()
        print(f"Total checkboxes: {len(cbs)}")
        for idx, cb in enumerate(cbs[:15]):
            try:
                txt = cb.locator("xpath=..").inner_text(timeout=800).strip()
                print(f"CB#{idx}: checked={cb.is_checked()}, text={txt[:40]!r}")
            except Exception:
                pass

        print("\n=== Radios de filtros disponibles ===")
        radios = frame.locator("input[type='radio']").all()
        print(f"Total radios: {len(radios)}")

        browser.close()
        print("Listo, screenshot en scratch_new_bonus_view.png")

if __name__ == '__main__':
    main()
