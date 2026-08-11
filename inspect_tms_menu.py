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

        page.goto(URL, timeout=45000)
        time.sleep(2)
        page.locator("a", has_text="Log in").first.click()
        time.sleep(2)
        page.fill("input[name='username']", USER)
        page.fill("input[name='pwd']", PASSWORD)
        page.locator("input[name='b_login']").click()
        time.sleep(3)
        print("Login OK. URL:", page.url)

        print("Hover/clic en 'Internet Service'...")
        internet_service = page.locator("a, li", has_text="Internet Service").first
        internet_service.click(force=True)
        time.sleep(1)
        page.screenshot(path="./scratch_tms_menu_open.png")

        print("\n=== Items visibles tras abrir el menu ===")
        items = page.locator("a").all()
        for item in items:
            try:
                text = item.inner_text(timeout=200).strip()
                href = item.get_attribute("href")
                if text and len(text) < 50:
                    print(f"  {text!r} -> {href}")
            except Exception:
                pass

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
