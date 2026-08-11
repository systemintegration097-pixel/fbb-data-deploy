import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

CNOC_URL = "http://10.121.184.131:8888/#/dashboard"
USER = "vtp_juan.vargas"
PASSWORD = "Fbb@07.2026"

def login_with_retry(page, max_attempts=4):
    page.goto(CNOC_URL, timeout=45000)
    for attempt in range(1, max_attempts + 1):
        try:
            page.wait_for_selector("#username", timeout=8000)
        except Exception:
            return True
        page.fill("#username", USER)
        page.fill("#password", PASSWORD)
        page.click("input[type='submit']")
        time.sleep(4)
        try:
            page.wait_for_selector("#username", timeout=6000)
            print(f"  Intento {attempt}: rebota, reintentando...")
            continue
        except Exception:
            return True
    return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()

        if not login_with_retry(page):
            print("No se pudo iniciar sesion.")
            browser.close()
            return
        print("Login OK.")
        time.sleep(8)

        wo_link = page.locator("a, li, span").filter(has_text="WO Management").first
        wo_link.click()
        time.sleep(6)
        print("En WO Management. URL:", page.url)

        # --- Abrir dropdown de Status ---
        print("\n=== Abriendo dropdown de WO Status (custom-statusSearchWeb) ===")
        try:
            indicator = page.locator(".react-Selector__control:has(#custom-statusSearchWeb)").locator("[class*='dropdown-indicator']").first
            indicator.click(force=True, timeout=5000)
            time.sleep(1)
            options = page.locator("div[class*='react-Selector__option']").all()
            print(f"Opciones encontradas: {len(options)}")
            for o in options:
                try:
                    print("  OPTION:", o.inner_text(timeout=300).strip())
                except Exception:
                    pass
        except Exception as e:
            print(f"Error abriendo dropdown status: {e}")

        page.screenshot(path="./scratch_cnoc_status_dropdown.png")

        # cerrar dropdown haciendo click afuera
        page.keyboard.press("Escape")
        time.sleep(1)

        # --- Abrir calendario de fecha ---
        print("\n=== Abriendo selector de fecha (date-range-toggle) ===")
        try:
            page.locator("button.date-range-toggle").first.click(force=True, timeout=5000)
            time.sleep(1)
            page.screenshot(path="./scratch_cnoc_date_popover.png")
            start_input = page.locator("input#DateTimeInput_start")
            end_input = page.locator("input#DateTimeInput_end")
            print("DateTimeInput_start existe:", start_input.count() > 0)
            print("DateTimeInput_end existe:", end_input.count() > 0)
        except Exception as e:
            print(f"Error abriendo calendario: {e}")

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
