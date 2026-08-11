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
        print("Login OK.")

        print("Clicando boton 'Internet Service'...")
        page.locator("button.bmenu", has_text="Internet Service").first.click()
        time.sleep(1.5)
        page.screenshot(path="./scratch_tms_menu_open2.png")

        print("\n=== Items del submenu (buscando FTTH) ===")
        menu_items = page.locator(".x-menu-item, .x-menu-item-text, td.x-menu-item").all()
        print(f"Total items tipo x-menu-item: {len(menu_items)}")
        for item in menu_items:
            try:
                text = item.inner_text(timeout=200).strip()
                if text:
                    print(f"  '{text}'")
            except Exception:
                pass

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
