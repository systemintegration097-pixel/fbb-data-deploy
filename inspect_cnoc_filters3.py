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
        print("Login OK. Esperando a que el SPA renderice (hasta 40s)...")
        try:
            page.wait_for_selector("text=WO Management", timeout=40000)
            print("  'WO Management' visible en el sidebar.")
        except Exception as e:
            print(f"  [Aviso] No aparecio 'WO Management' tras 40s: {e}")
        page.screenshot(path="./scratch_cnoc_postlogin.png")

        # Dismiss possible "Keep using" overlay
        try:
            keep_btn = page.locator("button:has-text('Keep using')")
            if keep_btn.count() > 0 and keep_btn.first.is_visible():
                print("Cerrando overlay 'Keep using'...")
                keep_btn.first.click(force=True)
                time.sleep(2)
        except Exception:
            pass

        print("Haciendo clic en el enlace 'WO Management' del sidebar...")
        try:
            wo_link = page.locator("a, li, span").filter(has_text="WO Management").first
            wo_link.click(timeout=15000)
            time.sleep(6)
        except Exception as e:
            print(f"Error haciendo clic en WO Management: {e}")

        page.screenshot(path="./scratch_cnoc_wo_direct.png")
        print("URL actual:", page.url)

        has_wocode = page.locator("input#input-filter-woCode").count() > 0
        print("Input woCode presente:", has_wocode)

        if not has_wocode:
            print("No se cargo la pagina de WO Management correctamente. Abortando exploracion de filtros.")
            browser.close()
            return

        print("\n=== Abriendo dropdown de WO Status ===")
        try:
            indicator = page.locator(".react-Selector__control:has(#custom-statusSearchWeb)").locator("[class*='dropdown-indicator']").first
            indicator.click(force=True, timeout=8000)
            time.sleep(1)
            options = page.locator("div[class*='react-Selector__option']").all()
            print(f"Opciones encontradas: {len(options)}")
            for o in options:
                try:
                    print("  OPTION:", o.inner_text(timeout=300).strip())
                except Exception:
                    pass
            page.screenshot(path="./scratch_cnoc_status_dropdown.png")
        except Exception as e:
            print(f"Error abriendo dropdown status: {e}")

        page.keyboard.press("Escape")
        time.sleep(1)

        print("\n=== Abriendo selector de fecha ===")
        try:
            page.locator("button.date-range-toggle").first.click(force=True, timeout=8000)
            time.sleep(1)
            page.screenshot(path="./scratch_cnoc_date_popover.png")
            print("DateTimeInput_start count:", page.locator("input#DateTimeInput_start").count())
            print("DateTimeInput_end count:", page.locator("input#DateTimeInput_end").count())
        except Exception as e:
            print(f"Error abriendo calendario: {e}")

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
