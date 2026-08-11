import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

URL = "http://10.121.62.102:8080/backup/?target=error&err=denied"
USER = "fbb"
PASSWORD = "100885aQ@"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()
        page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))

        page.goto(URL, timeout=45000)
        time.sleep(2)
        page.locator("a", has_text="Log in").first.click()
        time.sleep(2)

        print("Llenando credenciales (unico intento)...")
        page.fill("input[name='username']", USER)
        page.fill("input[name='pwd']", PASSWORD)
        page.locator("input[name='b_login']").click()
        time.sleep(3)
        print("URL tras login:", page.url)
        page.screenshot(path="./scratch_tms_after_login.png")

        body_text = page.inner_text("body")
        lower = body_text.lower()
        error_keywords = ["incorrect", "invalid", "incorrecto", "invalido", "denied", "denegado", "wrong"]
        found_errors = [k for k in error_keywords if k in lower]
        print("Posibles errores de login:", found_errors)

        print("\n=== Menu superior tras login ===")
        top_items = page.locator("li, a").all()
        seen = set()
        for item in top_items[:150]:
            try:
                text = item.inner_text(timeout=200).strip()
                if text and text not in seen and len(text) < 40 and "\n" not in text:
                    seen.add(text)
            except Exception:
                pass
        for t in seen:
            print(" ", t)

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
