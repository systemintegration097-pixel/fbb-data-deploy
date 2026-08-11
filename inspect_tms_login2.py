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

        print(f"Navegando a: {URL}")
        page.goto(URL, timeout=45000)
        time.sleep(3)
        print("URL actual:", page.url)
        print("Titulo:", page.title())
        page.screenshot(path="./scratch_tms_initial2.png")

        print("\n=== Links visibles ===")
        links = page.locator("a").all()
        for l in links[:40]:
            try:
                text = l.inner_text(timeout=300).strip()
                href = l.get_attribute("href")
                if text:
                    print(f"  {text!r} -> {href}")
            except Exception:
                pass

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
