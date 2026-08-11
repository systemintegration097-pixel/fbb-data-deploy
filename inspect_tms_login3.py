import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

URL = "http://10.121.62.102:8080/backup/?target=error&err=denied"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()
        page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))

        page.goto(URL, timeout=45000)
        time.sleep(2)

        print("Clicando 'Log in'...")
        page.locator("a", has_text="Log in").first.click()
        time.sleep(3)
        print("URL actual:", page.url)
        page.screenshot(path="./scratch_tms_loginform.png")

        print("\n=== Inputs del formulario ===")
        inputs = page.locator("input").all()
        for i, inp in enumerate(inputs):
            try:
                print(f"  input#{i}: type={inp.get_attribute('type')}, id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}")
            except Exception:
                pass

        print("\n=== Botones ===")
        buttons = page.locator("button, input[type='submit']").all()
        for i, b in enumerate(buttons):
            try:
                print(f"  btn#{i}: text={b.inner_text(timeout=300) if b.evaluate('el=>el.tagName')=='BUTTON' else b.get_attribute('value')!r}")
            except Exception as e:
                print(f"  btn#{i}: error {e}")

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
