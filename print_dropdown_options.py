import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(dotenv_path="c:\\Users\\jjvar\\OneDrive\\BITEL\\NEW INTERFACE\\.env")

USER = os.getenv("INTRANET_USER")
PASSWORD = os.getenv("INTRANET_PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
WO_MANAGEMENT_URL = "https://gnoc.viettel.vn:9000/#/wo/woManagement"

print("Imprimiendo opciones reales del dropdown de WO status...")
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--host-rules=MAP gnoc.viettel.vn 10.255.58.201, MAP sso2.viettel.vn 10.255.58.201, MAP auth.viettel.vn 171.252.201.181"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
    
    page.wait_for_url("**/dashboard", timeout=60000)
    page.wait_for_timeout(4000)
    
    # Navegar a WO
    page.goto(WO_MANAGEMENT_URL)
    page.wait_for_selector("input#input-filter-woCode", timeout=60000)
    
    try:
        page.wait_for_selector("#id-loading-overlay", state="hidden", timeout=30000)
    except:
        pass
    page.wait_for_timeout(4000)
    
    # Abrir dropdown
    dropdown_container = page.locator("div:has(> #custom-statusSearchWeb)").first
    dropdown_container.click(force=True)
    page.wait_for_timeout(2000)
    
    # Buscar opciones por clase 'react-select' o elementos de lista
    print("\nBuscando elementos con clase react-select o select-option:")
    options = page.locator("div[class*='react-Selector__option'], div[class*='option'], [role='option'], li").all()
    
    found_any = False
    for idx, opt in enumerate(options):
        try:
            text = opt.inner_text().strip()
            # Omitimos opciones vacías o de menú lateral
            if text and len(text) < 40:
                print(f"  [{idx}] Texto opción: '{text}'")
                found_any = True
        except:
            continue
            
    if not found_any:
        print("No se encontraron opciones visibles en el DOM por selectores comunes. Capturando pantalla...")
        screenshot_path = "C:\\Users\\jjvar\\.gemini\\antigravity-ide\\brain\\59ce769f-dd63-46e1-bb61-e10fb7442f08\\screenshot_dropdown_elements.png"
        page.screenshot(path=screenshot_path)
        print(f"Captura guardada en: {screenshot_path}")
        
    browser.close()
