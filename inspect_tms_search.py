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

        page.locator("button.bmenu", has_text="Internet Service").first.click()
        time.sleep(1)
        page.locator(".x-menu-item", has_text="FTTH Service").first.hover()
        time.sleep(1)
        print("Clicando 'Account on AAA'...")
        page.locator(".x-menu-item", has_text="Account on AAA").first.click()
        time.sleep(3)
        page.screenshot(path="./scratch_tms_search_page.png")

        print("\n=== Inputs/Selects en la pagina de busqueda ===")
        inputs = page.locator("input").all()
        for i, inp in enumerate(inputs):
            try:
                itype = inp.get_attribute('type')
                iname = inp.get_attribute('name')
                iid = inp.get_attribute('id')
                if itype not in (None, 'hidden') or iname or iid:
                    print(f"  input#{i}: type={itype}, id={iid}, name={iname}")
            except Exception:
                pass

        selects = page.locator("select").all()
        for i, sel in enumerate(selects):
            try:
                print(f"  select#{i}: id={sel.get_attribute('id')}, name={sel.get_attribute('name')}")
                opts = sel.locator("option").all()
                for o in opts[:10]:
                    print(f"      option: {o.get_attribute('value')!r} = {o.inner_text()!r}")
            except Exception:
                pass

        buttons = page.locator("button, a.x-btn-text, td.x-btn-mc").all()
        print("\n=== Botones ===")
        for b in buttons[:30]:
            try:
                t = b.inner_text(timeout=200).strip()
                if t:
                    print(f"  '{t}'")
            except Exception:
                pass

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
