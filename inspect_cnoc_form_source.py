import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

CNOC_URL = "http://10.121.184.131:8888/#/dashboard"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, ignore_https_errors=True)
        page = context.new_page()
        page.goto(CNOC_URL, timeout=45000)
        page.wait_for_selector("#username", timeout=15000)

        # NO llenar ni enviar nada. Solo inspeccionar el formulario y scripts.
        form_html = page.evaluate("""() => {
            const form = document.querySelector('form');
            return form ? form.outerHTML : 'NO FORM FOUND';
        }""")
        print("=== FORM HTML ===")
        print(form_html[:3000])

        print("\n=== SCRIPT TAGS (src) ===")
        scripts = page.locator("script").all()
        for s in scripts:
            src = s.get_attribute("src")
            if src:
                print(" ", src)

        print("\n=== onsubmit / inline scripts relacionados a password ===")
        inline = page.evaluate("""() => {
            const scripts = Array.from(document.querySelectorAll('script:not([src])'));
            return scripts.map(s => s.textContent).join('\\n---SCRIPT---\\n');
        }""")
        print(inline[:4000])

        browser.close()

if __name__ == '__main__':
    main()
