import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

CNOC_URL = "http://10.121.184.131:8888/#/dashboard"
USER = "vtp_juan.vargas"
PASSWORD = "Fbb@07.2026"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()
        page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))

        print(f"Navegando a: {CNOC_URL}")
        page.goto(CNOC_URL, timeout=45000)
        page.wait_for_selector("#username", timeout=15000)
        print("Llenando credenciales (unico intento de esta sesion)...")
        page.fill("#username", USER)
        page.fill("#password", PASSWORD)
        page.click("input[type='submit']")

        # Esperar activamente a que la URL cambie a algo que no sea el login, sin sleep fijo largo
        try:
            page.wait_for_url(lambda url: "passportv3/login" not in url, timeout=30000)
            print("Login exitoso, URL:", page.url)
        except Exception as e:
            print(f"[AVISO] No se detecto cambio de URL tras login: {e}")
            print("URL actual:", page.url)
            page.screenshot(path="./scratch_cnoc_full_loginfail.png")
            browser.close()
            return

        # Esperar a que el dashboard SPA cargue
        time.sleep(10)
        print("URL final tras carga:", page.url)
        page.screenshot(path="./scratch_cnoc_full_dashboard.png")

        # Explorar menu/navegacion (sidebar tipico)
        print("\n=== Enlaces/nav visibles ===")
        links = page.locator("a, [class*='nav'], [class*='menu-item']").all()
        seen = set()
        for l in links[:80]:
            try:
                text = l.inner_text(timeout=300).strip()
                if text and text not in seen and len(text) < 60:
                    seen.add(text)
                    print(f"  {text!r}")
            except Exception:
                pass

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
