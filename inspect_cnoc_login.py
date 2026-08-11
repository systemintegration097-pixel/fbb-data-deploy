import os
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
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))
        page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}") if msg.type == "error" else None)

        print(f"Navegando a: {CNOC_URL}")
        try:
            page.goto(CNOC_URL, timeout=45000)
        except Exception as e:
            print(f"Error en goto: {e}")
        time.sleep(3)
        page.screenshot(path="./scratch_cnoc_initial.png")
        print("URL actual:", page.url)
        print("Titulo:", page.title())

        # Dump de inputs visibles para entender el formulario de login
        inputs = page.locator("input").all()
        print(f"\nTotal inputs en pagina: {len(inputs)}")
        for i, inp in enumerate(inputs):
            try:
                print(f"  input#{i}: type={inp.get_attribute('type')}, id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}")
            except Exception as e:
                print(f"  input#{i}: error {e}")

        buttons = page.locator("button").all()
        print(f"\nTotal buttons en pagina: {len(buttons)}")
        for i, b in enumerate(buttons[:20]):
            try:
                print(f"  button#{i}: text={b.inner_text(timeout=500)!r}, id={b.get_attribute('id')}")
            except Exception:
                pass

        browser.close()
        print("\nListo. Screenshot: scratch_cnoc_initial.png")

if __name__ == '__main__':
    main()
