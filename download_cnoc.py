import os
import sys
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Cargar variables de entorno desde el archivo .env (forzando override para refrescar cambios)
load_dotenv(override=True)

CNOC_URL = os.getenv("CNOC_LOGIN_URL", "http://10.121.184.131:8888/#/dashboard")
CNOC_USER = os.getenv("CNOC_USER")
CNOC_PASSWORD = os.getenv("CNOC_PASSWORD")
WO_MANAGEMENT_LINK_TEXT = "WO Management"

# Valores de filtrado (mismo criterio que GNOC: código, nombre, y ahora TODOS los estados)
FILTER_WO_CODE = os.getenv("CNOC_FILTER_WO_CODE", "WO_SPM_20")
FILTER_WO_NAME = os.getenv("CNOC_FILTER_WO_NAME", "gftth")

# Estados disponibles en el selector de WO Status de CNOC (confirmado navegando en vivo el
# 2026-08-05). A diferencia de GNOC -que separa Pendientes vs Cerradas en búsquedas distintas-
# acá el pedido es una sola descarga con TODOS los estados marcados; la distinción entre
# "pendiente" (FT Inprocessing/Pending, se matchea con Tableau) y "cerrada/otro" (el resto, solo
# sirve para tipificación) se hace después en process_data.py por wo_status, no aquí.
ALL_WO_STATUSES = [
    "Wait CD receive", "CD received", "FT reject", "FT assigned", "FT received",
    "FT Inprocessing", "Closed FT", "Draft", "Closed", "Pending", "CD reject",
    "woManagement.label.Approve", "Refuse approve",
]

# Mismo mecanismo de ventana móvil que GNOC (ver download_report.py) para que el selector de
# meses del dashboard controle ambas fuentes por igual ("el resto de procesos con las WO de
# CNOC es lo mismo que GNOC", incluyendo el rango de fechas solicitado).
GNOC_LOOKBACK_DAYS = int(os.getenv("GNOC_LOOKBACK_DAYS", "60"))

def format_date_range(start_dt, end_dt):
    return f"{start_dt.strftime('%d/%m/%Y %H:%M:%S')} to {end_dt.strftime('%d/%m/%Y %H:%M:%S')}"

def compute_rolling_filter_create_time(lookback_days):
    end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    start_dt = (end_dt - timedelta(days=lookback_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return format_date_range(start_dt, end_dt)

# Permite fijar un rango manual vía FILTER_CREATE_TIME en .env; si no está seteado (caso normal),
# server.py lo pasa como override de entorno según lo elegido en el selector de meses del
# dashboard, igual que a GNOC.
FILTER_CREATE_TIME = os.getenv("FILTER_CREATE_TIME") or compute_rolling_filter_create_time(GNOC_LOOKBACK_DAYS)

def print_log(msg):
    print(msg, flush=True)

async def wait_for_loading_overlay(page, timeout=30000):
    try:
        await page.wait_for_selector("#id-loading-overlay", state="hidden", timeout=timeout)
        await asyncio.sleep(1)
    except Exception as e:
        print_log(f"  [Aviso] Espera de overlay de carga superada o ignorada: {e}")

async def fill_filter(page, column_name, value):
    if not value:
        print_log(f"Filtro '{column_name}' vacío, se omite.")
        return True

    print_log(f"Configurando filtro para '{column_name}' -> '{value}'")
    selectors = {
        "WO code": "input#input-filter-woCode",
        "WO name": "input#input-filter-woContent",
    }
    sel = selectors.get(column_name)
    if sel:
        try:
            await wait_for_loading_overlay(page)
            loc = page.locator(sel)
            if await loc.count() > 0:
                await loc.first.click(force=True)
                await loc.first.fill(value)
                print_log(f"  Llenado con éxito usando id: '{sel}'")
                return True
        except Exception as e:
            print_log(f"  Error al llenar {column_name}: {e}")

    print_log(f"  [ADVERTENCIA] No se pudo configurar el filtro para la columna: '{column_name}'")
    return False

async def select_wo_status(page, statuses_to_select):
    if not statuses_to_select:
        return True

    print_log(f"Configurando WO status a: {statuses_to_select}")
    await wait_for_loading_overlay(page)

    async def open_menu():
        menu = page.locator("div[class*='react-Selector__menu']").first
        if await menu.count() == 0 or not await menu.is_visible():
            indicator = page.locator(".react-Selector__control:has(#custom-statusSearchWeb)").locator("[class*='dropdown-indicator']").first
            await indicator.click(force=True)
            await asyncio.sleep(1)

    async def clear_search_input():
        input_el = page.locator("input#custom-statusSearchWeb").first
        await input_el.focus()
        val = await input_el.input_value()
        if val:
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await asyncio.sleep(0.3)

    async def select_exact(status_text):
        await open_menu()
        await clear_search_input()
        await page.keyboard.type(status_text)
        await asyncio.sleep(1)
        option = page.locator("div[class*='react-Selector__option']").get_by_text(status_text, exact=True).first
        if await option.count() > 0:
            await option.click(force=True)
            print_log(f"  Estado '{status_text}' seleccionado.")
            await asyncio.sleep(0.6)
            return True
        print_log(f"  [Advertencia] No se encontró la opción exacta para: '{status_text}'")
        return False

    try:
        status_control = page.locator(".react-Selector__control:has(#custom-statusSearchWeb)")
        clear_btn = status_control.locator("[class*='clear-indicator']").first
        if await clear_btn.count() > 0 and await clear_btn.is_visible():
            print_log("  Limpiando selecciones previas de estado mediante clear-indicator...")
            await clear_btn.click(force=True)
            await asyncio.sleep(1)

        remove_btns = await status_control.locator("[class*='multi-value__remove']").all()
        if remove_btns:
            print_log(f"  Removiendo {len(remove_btns)} píldoras de selección previas de status...")
            for btn in remove_btns:
                try:
                    await btn.click(force=True)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

        for status in statuses_to_select:
            await select_exact(status)

        return True
    except Exception as e:
        print_log(f"  Error al configurar WO status: {e}")
    return False

async def configure_date_range(page, date_range_str):
    if not date_range_str:
        return True

    print_log(f"Configurando rango de fechas -> '{date_range_str}'")
    await wait_for_loading_overlay(page)

    try:
        start_date = ""
        end_date = ""

        if date_range_str.lower().startswith("to "):
            start_date = ""
            end_date = date_range_str[3:].strip()
        elif " to " in date_range_str:
            parts = date_range_str.split(" to ")
            start_date = parts[0].strip()
            end_date = parts[1].strip()
        else:
            print_log(f"  [ERROR] El formato de fecha '{date_range_str}' no es un rango válido.")
            return False

        print_log(f"  Rango interpretado -> Inicio: '{start_date}' | Fin: '{end_date}'")

        print_log("  Abriendo popover de calendario...")
        popover_opened = False
        for attempt in range(1, 4):
            try:
                await page.locator("button.date-range-toggle").first.click(force=True)
                await page.wait_for_selector("input#DateTimeInput_start", timeout=8000)
                popover_opened = True
                print_log("  Popover de calendario abierto.")
                break
            except Exception:
                print_log(f"  Intento {attempt} de abrir calendario falló, reintentando click...")
                await asyncio.sleep(1)

        if not popover_opened:
            print_log("  [ERROR] No se pudo abrir el popover del calendario.")
            return False

        if start_date:
            await page.fill("input#DateTimeInput_start", start_date)
        await page.fill("input#DateTimeInput_end", end_date)

        print_log("  Presionando botón 'Apply'...")
        await page.locator("button:has-text('Apply')").first.click(force=True)
        await asyncio.sleep(2)

        final_val = await page.locator("input#custom-createDate").input_value()
        print_log(f"  Valor resultante en input principal: '{final_val}'")
        return True

    except Exception as e:
        print_log(f"  Error al configurar rango de fecha: {e}")
        return False

async def run_search_and_export(page, statuses, date_range_str, download_path, overlay_timeout=60000, download_timeout=300000):
    await configure_date_range(page, date_range_str)
    await select_wo_status(page, statuses)

    print_log(f"Haciendo clic en el botón 'Search' (rango: '{date_range_str}')...")
    await wait_for_loading_overlay(page)
    await page.locator("button:has-text('Search')").first.click()

    print_log("Esperando a que la tabla de resultados termine de cargar...")
    for _ in range(30):
        if await page.locator("#id-loading-overlay").is_visible() or await page.locator("text=Loading...").first.is_visible():
            print_log("  Se detectó el inicio de la carga de resultados.")
            break
        await asyncio.sleep(0.1)

    try:
        if await page.locator("#id-loading-overlay").count() > 0:
            await page.locator("#id-loading-overlay").first.wait_for(state="hidden", timeout=overlay_timeout)
        if await page.locator("text=Loading...").count() > 0:
            await page.locator("text=Loading...").first.wait_for(state="hidden", timeout=overlay_timeout)
        print_log("  ¡Los resultados terminaron de cargar en la tabla con éxito!")
    except Exception as e:
        print_log(f"  Advertencia al esperar fin de carga de la tabla: {e}")

    await asyncio.sleep(4)
    await wait_for_loading_overlay(page, timeout=overlay_timeout)

    # El portal (misma familia que GNOC) a veces falla la exportación con un toast "Export fail"
    # y hay que reintentar el clic varias veces hasta que funcione -confirmado probando a mano en
    # GNOC, muy probablemente igual acá dado que comparten la misma plantilla de WO Management-.
    # Reintentar el CLIC varias veces con espera corta es mucho más rápido que un timeout largo
    # único y evita reiniciar todo el flujo (login incluido) por algo que se resuelve solo.
    print_log(f"Iniciando la descarga haciendo clic en 'Export' -> {download_path}...")
    export_click_retries = 6
    export_click_timeout = 30000
    download = None
    last_error = None
    for click_attempt in range(1, export_click_retries + 1):
        try:
            async with page.expect_download(timeout=export_click_timeout) as download_info:
                await page.locator("button[title='Export']").first.click(force=True)
            download = await download_info.value
            last_error = None
            break
        except Exception as e:
            last_error = e
            print_log(f"  [Intento {click_attempt}/{export_click_retries}] El clic en 'Export' no generó descarga (probable 'Export fail' del portal), reintentando...")
            await asyncio.sleep(2)

    if last_error:
        print_log(f"Error durante el proceso de descarga ({download_path}): {last_error}")
        await page.screenshot(path="./screenshot_cnoc_download_error.png")
        raise last_error

    try:
        if os.path.exists(download_path):
            try:
                with open(download_path, "r+"):
                    pass
            except PermissionError:
                raise Exception(f"El archivo '{download_path}' está abierto en Microsoft Excel u otro programa. Por favor, ciérralo antes de sincronizar.")

        await download.save_as(download_path)
        print_log(f"\n[ÉXITO] ¡Reporte de CNOC guardado en: {download_path}!")
    except Exception as e:
        print_log(f"Error al guardar el archivo descargado ({download_path}): {e}")
        await page.screenshot(path="./screenshot_cnoc_download_error.png")
        raise e

async def login_cnoc(page, max_bounce_attempts=4):
    """Login a CNOC (Bitel Passport, CAS clásico). Comportamiento CONOCIDO y confirmado por el
    usuario: a veces la pantalla de login reaparece sin motivo tras enviar credenciales
    correctas -simplemente se vuelve a intentar y funciona-, así que se reintenta unas pocas
    veces. OJO: la cuenta se bloquea tras 5 intentos fallidos reales por día -> este límite se
    mantiene bajo (4) y, a diferencia de GNOC, el flujo NO vuelve a intentar login desde un nivel
    superior si esto se agota (ver run_flow) para no multiplicar los envíos de credenciales."""
    await page.goto(CNOC_URL, timeout=45000)
    for attempt in range(1, max_bounce_attempts + 1):
        try:
            await page.wait_for_selector("#username", timeout=10000)
        except Exception:
            print_log("Sesión ya autenticada (no apareció formulario de login).")
            return True

        print_log(f"  Intento {attempt}/{max_bounce_attempts} de login CNOC...")
        await page.fill("#username", CNOC_USER)
        await page.fill("#password", CNOC_PASSWORD)
        try:
            # El clic en sí puede quedar esperando "scheduled navigations to finish" hasta 30s
            # y tirar TimeoutError sin que eso signifique que el login falló -el chequeo real de
            # éxito/rebote ya lo hace el wait_for_selector de abajo-, así que no debe escapar del
            # bucle de reintentos (confirmado: pasó justo esto en una sync real).
            await page.click("input[type='submit']", timeout=15000)
        except Exception as e:
            print_log(f"  [Aviso] El clic en 'Log in' tardó de más ({e}); verificando igual si la sesión avanzó...")
        await asyncio.sleep(4)
        try:
            await page.wait_for_selector("#username", timeout=6000)
            print_log("  La pantalla de login reapareció (comportamiento conocido de CNOC), reintentando...")
            continue
        except Exception:
            print_log("  Login CNOC exitoso.")
            return True
    return False

async def load_wo_management(page):
    print_log("Navegando a WO Management (CNOC)...")
    await page.wait_for_selector(f"text={WO_MANAGEMENT_LINK_TEXT}", timeout=40000)
    link = page.locator("a, li, span").filter(has_text=WO_MANAGEMENT_LINK_TEXT).first
    await link.click(timeout=15000)
    await page.wait_for_selector("input#input-filter-woCode", timeout=25000)
    print_log("  ¡WO Management (CNOC) cargado correctamente!")
    await fill_filter(page, "WO code", FILTER_WO_CODE)
    await fill_filter(page, "WO name", FILTER_WO_NAME)

async def run_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            accept_downloads=True,
            ignore_https_errors=True,
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        page.on("pageerror", lambda err: print_log(f"[BROWSER PAGE ERROR] {err}"))

        login_ok = await login_cnoc(page)
        if not login_ok:
            await page.screenshot(path="./screenshot_cnoc_login_error.png")
            await browser.close()
            # Mensaje explícito: si esto pasa de forma persistente (no solo el rebote conocido),
            # lo más probable es que CNOC_USER/CNOC_PASSWORD en .env estén desactualizados.
            raise Exception(
                "No se pudo iniciar sesión en CNOC tras varios intentos. Si el problema persiste, "
                "es probable que la contraseña de CNOC (CNOC_USER/CNOC_PASSWORD en .env) sea "
                "incorrecta y deba actualizarse."
            )

        # Reintentos SOLO para los pasos posteriores al login (nunca reenvían credenciales), para
        # no arriesgar el límite de 5 intentos fallidos/día de la cuenta ante un fallo no
        # relacionado con el login (ej. timeout cargando WO Management o el botón Export).
        max_step_attempts = 2
        for attempt in range(1, max_step_attempts + 1):
            try:
                await load_wo_management(page)
                await run_search_and_export(
                    page, ALL_WO_STATUSES, FILTER_CREATE_TIME, "./reporte_cnoc.xlsx",
                    overlay_timeout=60000, download_timeout=300000
                )
                break
            except Exception as e:
                print_log(f"  Intento {attempt}/{max_step_attempts} de WO Management/export falló: {e}")
                if attempt == max_step_attempts:
                    raise
                await asyncio.sleep(5)

        await browser.close()
        print_log("Proceso de CNOC finalizado.")

async def async_main():
    if not CNOC_USER or not CNOC_PASSWORD:
        print_log("Error: Verifica CNOC_USER y CNOC_PASSWORD en el archivo .env")
        raise ValueError("Credenciales de CNOC incompletas en el archivo .env")
    await run_flow()

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
