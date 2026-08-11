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
        page.fill("#username", USER)
        page.fill("#password", PASSWORD)
        page.click("input[type='submit']")
        print("Login enviado, esperando carga del dashboard...")
        time.sleep(15)
        print("URL:", page.url)
        page.screenshot(path="./scratch_cnoc_dashboard.png")

        # Buscar enlaces/menu de navegacion
        links = page.locator("a").all()
        print(f"\nTotal enlaces: {len(links)}")
        seen = set()
        for l in links:
            try:
                text = l.inner_text(timeout=300).strip()
                href = l.get_attribute("href")
                if text and text not in seen:
                    seen.add(text)
                    print(f"  LINK: {text!r} -> {href}")
            except Exception:
                pass

        browser.close()

if __name__ == '__main__':
    main()
