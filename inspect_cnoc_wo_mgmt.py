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
        print(f"Intento {attempt}/{max_attempts} de login...")
        page.fill("#username", USER)
        page.fill("#password", PASSWORD)
        page.click("input[type='submit']")
        time.sleep(4)
        try:
            page.wait_for_selector("#username", timeout=6000)
            print("  Volvio a aparecer login, reintentando...")
            continue
        except Exception:
            print("  Login exitoso.")
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

        time.sleep(8)
        print("Buscando enlace 'WO Management'...")
        wo_link = page.locator("a, li, span").filter(has_text="WO Management").first
        wo_link.click()
        time.sleep(6)
        print("URL tras clic:", page.url)
        page.screenshot(path="./scratch_cnoc_wo_mgmt.png")

        print("\n=== Inputs en la pagina de WO Management ===")
        inputs = page.locator("input").all()
        print(f"Total inputs: {len(inputs)}")
        for i, inp in enumerate(inputs):
            try:
                print(f"  input#{i}: type={inp.get_attribute('type')}, id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}, class={inp.get_attribute('class')}")
            except Exception:
                pass

        print("\n=== Selects en la pagina ===")
        selects = page.locator("select").all()
        print(f"Total selects: {len(selects)}")
        for i, sel in enumerate(selects):
            try:
                print(f"  select#{i}: id={sel.get_attribute('id')}, name={sel.get_attribute('name')}")
            except Exception:
                pass

        print("\n=== Botones visibles ===")
        buttons = page.locator("button").all()
        for i, b in enumerate(buttons[:30]):
            try:
                text = b.inner_text(timeout=300).strip()
                if text:
                    print(f"  button#{i}: {text!r}")
            except Exception:
                pass

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
