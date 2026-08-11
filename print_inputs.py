import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(dotenv_path="c:\\Users\\jjvar\\OneDrive\\BITEL\\NEW INTERFACE\\.env")

USER = os.getenv("INTRANET_USER")
PASSWORD = os.getenv("INTRANET_PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
WO_MANAGEMENT_URL = "https://gnoc.viettel.vn:9000/#/wo/woManagement"

print("Imprimiendo todos los inputs de la página...")
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
    
    # Login con reintentos
    login_loaded = False
    for attempt in range(1, 4):
        try:
            page.goto(LOGIN_URL, timeout=45000)
            page.wait_for_selector("#username", timeout=15000)
            login_loaded = True
            break
        except:
            page.wait_for_timeout(3000)
            
    if not login_loaded:
        browser.close()
        exit(1)
        
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
    
    # Imprimir todos los inputs
    print("\nInputs encontrados:")
    inputs = page.locator("input").all()
    for idx, inp in enumerate(inputs):
        try:
            id_val = inp.get_attribute("id")
            name_val = inp.get_attribute("name")
            class_val = inp.get_attribute("class")
            print(f"  [{idx}] ID: '{id_val}' | Name: '{name_val}' | Class: '{class_val}'")
        except:
            continue
            
    browser.close()
