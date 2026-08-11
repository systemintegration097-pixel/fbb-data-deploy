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

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(BONUS_URL, timeout=45000)
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
        cbs = frame.locator("input[type='checkbox']").all()
        print(f"Total checkboxes: {len(cbs)}")

        # CB #22 es el '(All)' de Month/Year segun la inspeccion anterior
        target_idx = 22
        cb = cbs[target_idx]

        print(f"\n=== Diagnostico CB #{target_idx} (se espera '(All)' de Month/Year) ===")
        for levels, label in [
            ("xpath=..", "1 nivel arriba"),
            ("xpath=../..", "2 niveles arriba"),
            ("xpath=../../..", "3 niveles arriba"),
            ("xpath=../../../..", "4 niveles arriba"),
        ]:
            try:
                text = cb.locator(levels).inner_text(timeout=1500).strip()
                print(f"{label} ({levels}): '{text[:120]}'")
            except Exception as e:
                print(f"{label} ({levels}): ERROR {e}")

        print(f"\nis_checked: {cb.is_checked()}")
        # Atributos utiles
        for attr in ("aria-label", "title", "id", "name", "value"):
            try:
                print(f"attr {attr}: {cb.get_attribute(attr)}")
            except Exception:
                pass

        # Tambien mostrar el HTML de los ancestros para ver la estructura real
        print("\n=== outerHTML del checkbox y ancestros (recortado) ===")
        try:
            html = cb.evaluate("""el => {
                let out = [];
                let node = el;
                for (let i = 0; i < 5 && node; i++) {
                    out.push('LEVEL ' + i + ': ' + node.outerHTML.slice(0, 300));
                    node = node.parentElement;
                }
                return out.join('\\n---\\n');
            }""")
            print(html)
        except Exception as e:
            print(f"Error obteniendo HTML: {e}")

        browser.close()

if __name__ == '__main__':
    main()
