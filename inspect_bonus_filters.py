import os
import sys
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

USER = os.getenv("TABLEAU_USER", "vtp_branch")
PASSWORD = os.getenv("TABLEAU_PASSWORD", "B1t3l@123")
BONUS_URL = os.getenv("TABLEAU_BONUS_URL", "http://10.121.43.82/#/views/12_BonusCommistion/Detail_Data_Implementation?:iid=1")

sys.stdout.reconfigure(encoding='utf-8')

def dump_filters():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        print(f"Navegando a: {BONUS_URL}")
        page.goto(BONUS_URL, timeout=45000)

        try:
            page.wait_for_selector("input[name='username']", timeout=10000)
            print("Formulario de login detectado, autenticando...")
            page.fill("input[name='username']", USER)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_selector("input[name='username']", state="detached", timeout=30000)
        except Exception as e:
            print(f"No se detecto/uso formulario de login (quizas ya autenticado): {e}")

        print("Esperando 25s renderizado inicial...")
        time.sleep(25)

        page.screenshot(path="./scratch_bonus_inspect.png")

        frame = page.frame_locator("iframe").first

        print("\n=== CHECKBOXES ===")
        checkboxes = frame.locator("input[type='checkbox']").all()
        print(f"Total checkboxes encontrados: {len(checkboxes)}")
        for idx, cb in enumerate(checkboxes):
            try:
                parent_text = ""
                for level in ("xpath=..", "xpath=../..", "xpath=../../.."):
                    try:
                        parent_text = cb.locator(level).inner_text(timeout=1000).strip()
                        if parent_text:
                            break
                    except Exception:
                        continue
                is_checked = cb.is_checked()
                print(f"CB #{idx}: checked={is_checked}, text='{parent_text[:60]}'")
            except Exception as e:
                print(f"CB #{idx} error: {e}")

        print("\n=== RADIO BUTTONS ===")
        radios = frame.locator("input[type='radio']").all()
        print(f"Total radios encontrados: {len(radios)}")
        for idx, rb in enumerate(radios):
            try:
                parent_text = ""
                for level in ("xpath=..", "xpath=../..", "xpath=../../.."):
                    try:
                        parent_text = rb.locator(level).inner_text(timeout=1000).strip()
                        if parent_text:
                            break
                    except Exception:
                        continue
                is_checked = rb.is_checked()
                name_attr = rb.get_attribute("name")
                print(f"RADIO #{idx}: checked={is_checked}, name='{name_attr}', text='{parent_text[:60]}'")
            except Exception as e:
                print(f"RADIO #{idx} error: {e}")

        print("\n=== BOTONES (Apply/Cancel/Aplicar) ===")
        buttons = frame.locator("button, div[role='button']").all()
        print(f"Total botones encontrados: {len(buttons)}")
        for idx, btn in enumerate(buttons):
            try:
                text = btn.inner_text(timeout=500).strip()
                if text and len(text) < 40:
                    print(f"BTN #{idx}: text='{text}'")
            except Exception:
                pass

        print("\n=== FILTER SECTION HEADERS (posibles titulos de filtro) ===")
        headers = frame.locator("[class*='filter'], [class*='Filter'], span[title], div[title]").all()
        seen = set()
        for idx, h in enumerate(headers[:200]):
            try:
                text = h.inner_text(timeout=500).strip()
                if text and text not in seen and len(text) < 60:
                    seen.add(text)
                    print(f"HDR: '{text}'")
            except Exception:
                pass

        browser.close()
        print("\nListo. Screenshot guardado en scratch_bonus_inspect.png")

if __name__ == '__main__':
    dump_filters()
