import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(dotenv_path="c:\\Users\\jjvar\\OneDrive\\BITEL\\NEW INTERFACE\\.env")

USER = os.getenv("INTRANET_USER")
PASSWORD = os.getenv("INTRANET_PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
WO_MANAGEMENT_URL = "https://gnoc.viettel.vn:9000/#/wo/woManagement"

print("Iniciando análisis de inputs del popover...")
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--host-rules=MAP gnoc.viettel.vn 10.255.58.201"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        accept_downloads=True,
        ignore_https_errors=True,
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    
    # Login
    page.goto(LOGIN_URL)
    page.wait_for_selector("#username")
    page.fill("#username", USER)
    page.fill("#password", PASSWORD)
    page.locator("#submit, input[type='submit'], button[type='submit']").first.click()
    
    password_button_selector = "button.password-button"
    page.wait_for_selector(password_button_selector)
    page.locator(password_button_selector).click()
    
    page.wait_for_selector("input#username")
    page.fill("input#username", USER)
    page.fill("input#password", PASSWORD)
    page.click("button#submitBtn")
    
    page.wait_for_url("**/dashboard")
    page.wait_for_timeout(3000)
    
    # Navegar a WO
    page.locator("a[href='#/wo/woManagement']").first.click()
    page.wait_for_selector("input#custom-createDate")
    
    # Abrir popover
    page.locator("button.date-range-toggle").first.click()
    page.wait_for_timeout(2000)
    
    # Listar todos los inputs de texto visibles
    print("\nTodos los inputs de texto visibles con el popover abierto:")
    inputs = page.locator("input").all()
    for idx, inp in enumerate(inputs):
        try:
            if inp.is_visible():
                val = inp.input_value()
                html = inp.evaluate("el => el.outerHTML")
                print(f"  [{idx}] Valor: '{val}' | HTML: '{html}'")
        except Exception as e:
            continue
            
    # Listar todos los botones visibles con el popover abierto
    print("\nTodos los botones visibles con el popover abierto:")
    buttons = page.locator("button, [role='button'], span, div").all()
    for idx, btn in enumerate(buttons):
        try:
            text = btn.inner_text().strip()
            if btn.is_visible() and text in ("Apply", "Clear", "Apply date", "Search"):
                html = btn.evaluate("el => el.outerHTML")
                print(f"  [{idx}] Texto: '{text}' | HTML: '{html}'")
        except Exception as e:
            continue
            
    browser.close()
