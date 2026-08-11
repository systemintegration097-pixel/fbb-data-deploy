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
        page.goto(CNOC_URL, timeout=45000)
        page.wait_for_selector("#username", timeout=15000)
        print("Login form detectado. Llenando UNA sola vez, con cuidado (cuenta se bloquea tras 5 intentos fallidos/dia)...")
        page.fill("#username", USER)
        page.fill("#password", PASSWORD)
        page.click("input[type='submit']")
        time.sleep(5)
        print("URL tras submit:", page.url)
        page.screenshot(path="./scratch_cnoc_after_login.png")

        # Buscar indicios de error de login (texto de error tipico de CAS)
        body_text = page.inner_text("body")
        lower = body_text.lower()
        error_keywords = ["incorrect", "invalid", "error", "failed", "incorrecto", "invalido", "bloque", "locked", "wrong"]
        found_errors = [k for k in error_keywords if k in lower]
        print("Palabras de posible error encontradas:", found_errors)
        print("\nPrimeros 500 caracteres del body:")
        print(body_text[:500])

        browser.close()

if __name__ == '__main__':
    main()
