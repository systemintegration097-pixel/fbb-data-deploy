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
        target_idx = 22
        cb = cbs[target_idx]

        # El elemento realmente interactivo es el div[role=checkbox] 2 niveles arriba
        wrapper = cb.locator("xpath=../..")
        print("aria-checked ANTES:", wrapper.get_attribute("aria-checked"))
        print("Clicando el div[role=checkbox] (no el input oculto)...")
        wrapper.click(force=True, timeout=5000)
        time.sleep(2)
        print("aria-checked DESPUES del click:", wrapper.get_attribute("aria-checked"))
        print("input.is_checked() DESPUES:", cb.is_checked())

        # Buscar botones Apply/Cancel visibles ahora
        print("\nBuscando boton 'Apply' visible...")
        apply_btn = frame.locator("button:has-text('Apply')")
        count = apply_btn.count()
        print(f"Botones 'Apply' encontrados: {count}")
        for i in range(count):
            try:
                visible = apply_btn.nth(i).is_visible()
                print(f"  Apply #{i}: visible={visible}")
            except Exception as e:
                print(f"  Apply #{i}: error {e}")

        if count > 0:
            for i in range(count):
                if apply_btn.nth(i).is_visible():
                    print(f"Clicando Apply #{i}...")
                    apply_btn.nth(i).click(force=True, timeout=5000)
                    time.sleep(3)
                    break

        time.sleep(5)
        print("\naria-checked FINAL (tras posible Apply):", wrapper.get_attribute("aria-checked"))
        print("input.is_checked() FINAL:", cb.is_checked())

        # Revisar tambien un mes reciente especifico (Nov 2025 deberia estar en algun otro indice ahora)
        cbs2 = frame.locator("input[type='checkbox']").all()
        print(f"\nTotal checkboxes tras el cambio: {len(cbs2)}")
        for idx, c in enumerate(cbs2):
            try:
                txt = c.locator("xpath=..").inner_text(timeout=800).strip()
                if "November 2025" in txt or "2026" in txt or txt == "(All)":
                    print(f"  CB #{idx}: checked={c.is_checked()}, text='{txt[:40]}'")
            except Exception:
                pass

        page.screenshot(path="./scratch_bonus_after_click.png")
        browser.close()

if __name__ == '__main__':
    main()
