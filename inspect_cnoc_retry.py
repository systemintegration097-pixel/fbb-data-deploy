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

        print(f"Navegando a: {CNOC_URL}")
        page.goto(CNOC_URL, timeout=45000)

        max_attempts = 4
        logged_in = False
        for attempt in range(1, max_attempts + 1):
            print(f"\nIntento {attempt}/{max_attempts}...")
            try:
                page.wait_for_selector("#username", timeout=10000)
            except Exception:
                print("No se encontro formulario de login, asumiendo que ya esta logueado.")
                logged_in = True
                break

            page.fill("#username", USER)
            page.fill("#password", PASSWORD)
            page.click("input[type='submit']")
            time.sleep(4)

            try:
                page.wait_for_selector("#username", timeout=6000)
                print(f"  Intento {attempt}: volvio a aparecer el login (comportamiento conocido, reintentando)...")
                continue
            except Exception:
                print(f"  Intento {attempt}: no volvio a aparecer el login. URL:", page.url)
                logged_in = True
                break

        if not logged_in:
            print("\nNo se logro iniciar sesion tras varios intentos.")
            page.screenshot(path="./scratch_cnoc_retry_fail.png")
            browser.close()
            return

        print("\nEsperando carga completa del dashboard...")
        time.sleep(10)
        print("URL final:", page.url)
        page.screenshot(path="./scratch_cnoc_retry_success.png")

        print("\n=== Enlaces/nav visibles ===")
        links = page.locator("a, [class*='nav'], [class*='menu']").all()
        seen = set()
        for l in links[:100]:
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
