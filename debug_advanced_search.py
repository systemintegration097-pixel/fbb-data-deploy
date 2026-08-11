import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

USER = os.getenv("INTRANET_USER")
PASSWORD = os.getenv("INTRANET_PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
WO_MANAGEMENT_URL = "https://gnoc.viettel.vn:9000/#/wo/woManagement"


def log(msg):
    print(msg, flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--host-rules=MAP gnoc.viettel.vn 10.255.58.201, MAP sso2.viettel.vn 10.255.58.201, MAP auth.viettel.vn 171.252.201.181"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ignore_https_errors=True,
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()

    log("Login paso 1...")
    page.goto(LOGIN_URL, timeout=45000)
    page.wait_for_selector("#username", timeout=15000)
    page.fill("#username", USER)
    page.fill("#password", PASSWORD)
    page.locator("#submit, input[type='submit'], button[type='submit']").first.click()

    log("Login paso 2...")
    page.wait_for_selector("button.password-button", timeout=20000)
    page.locator("button.password-button").click()
    page.wait_for_selector("input#username", timeout=20000)
    page.fill("input#username", USER)
    page.fill("input#password", PASSWORD)
    page.click("button#submitBtn")

    log("Esperando dashboard...")
    page.wait_for_url("**/dashboard", timeout=60000)
    page.wait_for_timeout(5000)

    log("Navegando a WO Management...")
    loaded = False
    for attempt in range(1, 4):
        try:
            page.goto(WO_MANAGEMENT_URL, timeout=45000)
            page.wait_for_selector("input#input-filter-woCode", timeout=25000)
            loaded = True
            break
        except Exception as e:
            log(f"  Intento {attempt} falló: {e}")
            page.wait_for_timeout(3000)
    if not loaded:
        raise Exception("No se pudo cargar WO Management tras 3 intentos")
    page.wait_for_timeout(2000)

    log("Buscando y haciendo clic en 'Advanced search'...")
    adv = page.locator("text=Advanced search").first
    if adv.count() > 0:
        adv.click(force=True)
        page.wait_for_timeout(2000)
        log("Clic en 'Advanced search' realizado.")
    else:
        log("No se encontró el texto 'Advanced search'.")

    page.screenshot(path="./debug_advanced_search.png", full_page=True)
    log("Screenshot guardado en ./debug_advanced_search.png")

    # También listar todos los checkboxes visibles con su texto de contexto
    cbs = page.locator("input[type='checkbox']").all()
    log(f"Checkboxes encontrados: {len(cbs)}")
    with open("debug_checkboxes.txt", "w", encoding="utf-8") as f:
        for i, cb in enumerate(cbs):
            try:
                txt = cb.locator("xpath=../..").inner_text().strip().replace("\n", " | ")
            except Exception as e:
                txt = f"(error: {e})"
            f.write(f"{i}: checked={cb.is_checked()} text='{txt}'\n")
    log("Detalle de checkboxes guardado en debug_checkboxes.txt")

    browser.close()
    log("Listo.")
