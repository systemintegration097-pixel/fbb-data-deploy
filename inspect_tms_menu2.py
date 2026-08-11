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

        # Dump nav HTML directly
        nav_html = page.evaluate("""() => {
            const navs = document.querySelectorAll('.nav, nav, ul');
            for (const n of navs) {
                if (n.textContent.includes('Internet Service')) {
                    return n.outerHTML;
                }
            }
            return 'NOT FOUND';
        }""")
        print("\n=== NAV HTML (recortado a 3000 chars) ===")
        print(nav_html[:3000])

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
