import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(dotenv_path="c:\\Users\\jjvar\\OneDrive\\BITEL\\NEW INTERFACE\\.env")

USER = os.getenv("INTRANET_USER")
PASSWORD = os.getenv("INTRANET_PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
WO_MANAGEMENT_URL = "https://gnoc.viettel.vn:9000/#/wo/woManagement"

print("Inspeccionando DOM del datepicker...")
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--host-rules=MAP gnoc.viettel.vn 10.255.58.201, MAP sso2.viettel.vn 10.255.58.201, MAP auth.viettel.vn 171.252.201.181"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        accept_downloads=True,
        ignore_https_errors=True,
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    
    # Login con reintento
    login_loaded = False
    for attempt in range(1, 4):
        try:
            print(f"Intento {attempt} de conectar SSO...")
            page.goto(LOGIN_URL, timeout=45000)
            page.wait_for_selector("#username", timeout=15000)
            login_loaded = True
            break
        except Exception as e:
            print(f"Error intento {attempt}: {e}")
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
    page.wait_for_timeout(5000)
    
    # Navegar a WO
    page.goto(WO_MANAGEMENT_URL)
    page.wait_for_selector("input#input-filter-woCode", timeout=60000)
    
    # Esperar overlay
    try:
        page.wait_for_selector("#id-loading-overlay", state="hidden", timeout=30000)
    except:
        pass
    page.wait_for_timeout(4000)
    
    # Imprimir HTML del datepicker y sus contenedores hermanos
    try:
        # Imprimir HTML del input de fecha
        html_input = page.locator("input#custom-createDate").evaluate("el => el.outerHTML")
        print("\nHTML del input #custom-createDate:")
        print(html_input)
        
        # Imprimir HTML del contenedor padre del input
        html_parent = page.locator("input#custom-createDate").evaluate("el => el.parentElement.outerHTML")
        print("\nHTML del parent del input:")
        print(html_parent[:1000])  # Primeros 1000 chars
        
        # Imprimir HTML del abuelo del input (para ver botones hermanos)
        html_grandparent = page.locator("input#custom-createDate").evaluate("el => el.parentElement.parentElement.outerHTML")
        print("\nHTML del grandparent del input:")
        print(html_grandparent[:1500])  # Primeros 1500 chars
        
    except Exception as e:
        print(f"Error al inspeccionar HTML: {e}")
        
    browser.close()
