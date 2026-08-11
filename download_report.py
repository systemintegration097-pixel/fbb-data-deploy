import os
import sys
import time
import asyncio
import glob
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Cargar variables de entorno desde el archivo .env (forzando override para refrescar cambios)
load_dotenv(override=True)

USER = os.getenv("INTRANET_USER")
PASSWORD = os.getenv("INTRANET_PASSWORD")
LOGIN_URL = os.getenv("LOGIN_URL")
WO_MANAGEMENT_URL = "https://gnoc.viettel.vn:9000/#/wo/woManagement"

# Valores de filtrado
FILTER_WO_CODE = os.getenv("FILTER_WO_CODE", "SPM_202")
FILTER_WO_NAME = os.getenv("FILTER_WO_NAME", "gftth")
FILTER_WO_STATUS = os.getenv("FILTER_WO_STATUS", "All option")

# Las WOs 'Closed'/'Closed FT' deben cubrir el mismo rango completo que las pendientes
# (mismo requisito de siempre: ni el mismo rango, no una ventana más angosta solo para Close),
# pero traerlas en una sola consulta satura el portal GNOC y la tabla nunca termina de cargar.
# Por eso se parte el rango completo en tramos de CLOSED_WO_CHUNK_DAYS días.
CLOSED_WO_CHUNK_DAYS = int(os.getenv("CLOSED_WO_CHUNK_DAYS", "7"))

# GNOC_LOOKBACK_DAYS: días hacia atrás desde hoy para ambas búsquedas (pendientes y cerradas).
# Antes FILTER_CREATE_TIME era un string fijo en .env ("01/06/2026 a 31/07/2026") que había que
# actualizar a mano; si solo se movía la fecha final sin mover también la inicial, el rango total
# crecía mes a mes y con CLOSED_WO_CHUNK_DAYS fijo en 7 cada vez salían más tramos secuenciales
# (9 tramos con el rango de 61 días que quedó fijado en julio) -> la sync tardaba cada vez más.
# Con una ventana móvil de N días recalculada en cada corrida, el número de tramos queda acotado
# para siempre. Se mantiene en 60 (el mismo tamaño que ya se venía usando) para no achicar la
# cobertura de datos respecto a lo que ya se pedía.
GNOC_LOOKBACK_DAYS = int(os.getenv("GNOC_LOOKBACK_DAYS", "60"))

def parse_filter_date_range(date_range_str):
    """Convierte 'DD/MM/YYYY HH:MM:SS to DD/MM/YYYY HH:MM:SS' en (start_dt, end_dt)."""
    start_str, end_str = date_range_str.split(" to ")
    start_dt = datetime.strptime(start_str.strip(), "%d/%m/%Y %H:%M:%S")
    end_dt = datetime.strptime(end_str.strip(), "%d/%m/%Y %H:%M:%S")
    return start_dt, end_dt

def generate_date_chunks(start_dt, end_dt, chunk_days):
    """Divide [start_dt, end_dt] en sub-rangos consecutivos de a lo sumo chunk_days días."""
    chunks = []
    cur = start_dt
    while cur < end_dt:
        chunk_end = min(cur + timedelta(days=chunk_days) - timedelta(seconds=1), end_dt)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(seconds=1)
    return chunks

def format_date_range(start_dt, end_dt):
    return f"{start_dt.strftime('%d/%m/%Y %H:%M:%S')} to {end_dt.strftime('%d/%m/%Y %H:%M:%S')}"

def compute_rolling_filter_create_time(lookback_days):
    """Ventana móvil: últimos `lookback_days` días hasta hoy, recalculada en cada corrida."""
    end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    start_dt = (end_dt - timedelta(days=lookback_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return format_date_range(start_dt, end_dt)

# Permite fijar un rango manual vía FILTER_CREATE_TIME en .env (pruebas/depuración); si no está
# seteado, se usa la ventana móvil de GNOC_LOOKBACK_DAYS días.
FILTER_CREATE_TIME = os.getenv("FILTER_CREATE_TIME") or compute_rolling_filter_create_time(GNOC_LOOKBACK_DAYS)

def print_log(msg):
    print(msg, flush=True)

async def wait_for_loading_overlay(page, timeout=30000):
    """Espera a que el overlay de carga se oculte por completo."""
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
        "WO name": "input#input-filter-woContent"
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
        """Selecciona una opción escribiendo su texto exacto. Usado para 'FT Inprocessing'."""
        await open_menu()
        await clear_search_input()
        await page.keyboard.type(status_text)
        await asyncio.sleep(1)
        option = page.locator("div[class*='react-Selector__option']").get_by_text(status_text, exact=True).first
        if await option.count() > 0:
            await option.click(force=True)
            print_log(f"  Estado '{status_text}' seleccionado.")
            await asyncio.sleep(0.8)
            return True
        print_log(f"  [Advertencia] No se encontró la opción exacta para: '{status_text}'")
        return False

    try:
        # 0. Limpiar selecciones previas
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
            
            if len(start_date) <= 2:
                end_parts = end_date.split("/")
                if len(end_parts) >= 3:
                    month = end_parts[1]
                    year_time = end_parts[2]
                    year = year_time.split()[0]
                    start_date = f"{start_date.zfill(2)}/{month}/{year} 00:00:00"
        else:
            print_log(f"  [ERROR] El formato de fecha '{date_range_str}' no es un rango válido.")
            return False
            
        print_log(f"  Rango interpretado -> Inicio: '{start_date}' | Fin: '{end_date}'")
        
        # 1. Abrir popover con reintentos
        print_log("  Abriendo popover de calendario...")
        popover_opened = False
        for attempt in range(1, 4):
            try:
                await page.locator("button.date-range-toggle").first.click(force=True)
                await page.wait_for_selector("input#DateTimeInput_start", timeout=8000)
                popover_opened = True
                print_log("  Popover de calendario abierto.")
                break
            except Exception as e:
                print_log(f"  Intento {attempt} de abrir calendario falló, reintentando click...")
                await asyncio.sleep(1)
                
        if not popover_opened:
            print_log("  [ERROR] No se pudo abrir el popover del calendario.")
            return False
            
        # 2. Rellenar inputs de fecha internos
        if start_date:
            await page.fill("input#DateTimeInput_start", start_date)
        else:
            await page.locator("input#DateTimeInput_start").focus()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await asyncio.sleep(0.5)
            
        await page.fill("input#DateTimeInput_end", end_date)
        
        # 3. Hacer clic en Apply dentro del popover
        print_log("  Presionando botón 'Apply'...")
        await page.locator("button:has-text('Apply')").first.click(force=True)
        await asyncio.sleep(2)
        
        # Validar si el campo principal reflejó la fecha
        final_val = await page.locator("input#custom-createDate").input_value()
        print_log(f"  Valor resultante en input principal: '{final_val}'")
        return True
        
    except Exception as e:
        print_log(f"  Error al configurar rango de fecha: {e}")
        return False

async def run_search_and_export(page, statuses, date_range_str, download_path, overlay_timeout=45000, download_timeout=180000):
    await configure_date_range(page, date_range_str)
    await select_wo_status(page, statuses)

    print_log(f"Haciendo clic en el botón 'Search' (estados: {statuses}, rango: '{date_range_str}')...")
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

    # --- Descargar el Excel ---
    # El portal a veces falla la exportación con un toast "Export fail" (confirmado probando a
    # mano) y hay que reintentar el clic varias veces hasta que funcione -no es un problema de
    # nuestro código: la búsqueda/filtros ya cargaron bien, es la exportación en sí la que a veces
    # no arranca-. Reintentar el CLIC varias veces con espera corta es mucho más rápido y
    # confiable que esperar un timeout largo una sola vez y recién ahí reiniciar todo el flujo
    # (login incluido) desde el nivel superior.
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
        await page.screenshot(path=f"./screenshot_download_error_{os.path.basename(download_path)}.png")
        raise last_error

    try:
        # Verificar si el archivo está bloqueado por Excel antes de guardar
        if os.path.exists(download_path):
            try:
                with open(download_path, "r+"):
                    pass
            except PermissionError:
                raise Exception(f"El archivo '{download_path}' está abierto en Microsoft Excel u otro programa. Por favor, ciérralo antes de sincronizar.")

        await download.save_as(download_path)
        print_log(f"\n[ÉXITO] ¡Reporte guardado en: {download_path}!")
    except Exception as e:
        print_log(f"Error al guardar el archivo descargado ({download_path}): {e}")
        await page.screenshot(path=f"./screenshot_download_error_{os.path.basename(download_path)}.png")
        raise e

async def run_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--host-rules=MAP gnoc.viettel.vn 10.255.58.201, MAP sso2.viettel.vn 10.255.58.201, MAP auth.viettel.vn 171.252.201.181"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            accept_downloads=True,
            ignore_https_errors=True,
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        page.on("pageerror", lambda err: print_log(f"[BROWSER PAGE ERROR] {err}"))
        
        # --- PASO 1: Login SSO Principal con reintentos ---
        print_log(f"Navegando a SSO: {LOGIN_URL}")
        login_loaded = False
        for attempt in range(1, 4):
            try:
                await page.goto(LOGIN_URL, timeout=45000)
                await page.wait_for_selector("#username", timeout=15000)
                login_loaded = True
                break
            except Exception as e:
                print_log(f"  Intento {attempt} de conectar al SSO falló: {e}")
                await asyncio.sleep(3)
                
        if not login_loaded:
            print_log("[ERROR CRÍTICO] No se pudo conectar a la intranet tras 3 intentos.")
            await browser.close()
            raise Exception("No se pudo conectar a la intranet tras 3 intentos de login SSO")
            
        print_log("Llenando credenciales del primer SSO...")
        await page.fill("#username", USER)
        await page.fill("#password", PASSWORD)
        await page.locator("#submit, input[type='submit'], button[type='submit']").first.click()
        
        # --- PASO 2: Segundo Login (auth.viettel.vn) ---
        print_log("Esperando botón de redirección de contraseña...")
        password_button_selector = "button.password-button"
        await page.wait_for_selector(password_button_selector, timeout=20000)
        await page.locator(password_button_selector).click()
        
        print_log("Llenando credenciales en la segunda página de login...")
        await page.wait_for_selector("input#username", timeout=20000)
        await page.fill("input#username", USER)
        await page.fill("input#password", PASSWORD)
        await page.click("button#submitBtn")
        
        # --- PASO 3: Esperar Autorización y redirección a Dashboard ---
        print_log("Esperando a que la sesión se autorice en el Dashboard...")
        try:
            await page.wait_for_url("**/dashboard", timeout=60000)
            print_log("¡Sesión autorizada en el Dashboard!")
            await asyncio.sleep(5)
        except Exception as e:
            print_log(f"Error al esperar la autorización de sesión: {e}")
            await page.screenshot(path="./screenshot_dashboard_error.png")
            await browser.close()
            # Si el login nunca redirige a /dashboard, lo más probable es que las credenciales
            # (INTRANET_USER/INTRANET_PASSWORD en .env, editables desde la sección Credenciales
            # del dashboard) sean incorrectas o la contraseña haya cambiado.
            raise Exception(
                "No se pudo autorizar la sesión en el Dashboard de GNOC. Es probable que la "
                f"contraseña de GNOC sea incorrecta y deba actualizarse (sección Credenciales). Detalle: {e}"
            )
            
        async def load_wo_management():
            print_log("Navegando a la sección WO Management...")
            for attempt in range(1, 4):
                print_log(f"  Intento {attempt} de cargar WO Management...")
                try:
                    await page.goto(WO_MANAGEMENT_URL, timeout=45000)
                    await page.wait_for_selector("input#input-filter-woCode", timeout=25000)
                    print_log("  ¡WO Management cargado correctamente!")
                    await fill_filter(page, "WO code", FILTER_WO_CODE)
                    await fill_filter(page, "WO name", FILTER_WO_NAME)
                    return
                except Exception as e:
                    print_log(f"  Error en intento {attempt}: {e}")
                    await asyncio.sleep(3)

            print_log("No se pudo cargar la sección WO Management después de 3 intentos.")
            await page.screenshot(path="./screenshot_wo_load_error.png")
            raise Exception("No se pudo cargar la sección WO Management tras reintentos")

        # --- PASO 4/5: Cargar WO Management y rellenar filtros base ---
        await load_wo_management()

        # --- PASO 6/7: Búsquedas independientes en la misma sesión ---
        # 1) Pendientes
        await run_search_and_export(
            page, ["FT Inprocessing"], FILTER_CREATE_TIME, "./reporte_gnoc.xlsx",
            overlay_timeout=45000, download_timeout=180000
        )

        # 2) Cerradas en tramos
        start_dt, end_dt = parse_filter_date_range(FILTER_CREATE_TIME)
        chunks = generate_date_chunks(start_dt, end_dt, CLOSED_WO_CHUNK_DAYS)
        print_log(f"Descargando WOs cerradas en {len(chunks)} tramo(s) de {CLOSED_WO_CHUNK_DAYS} día(s) cada uno...")
        for i, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            chunk_path = f"./reporte_gnoc_closed_{i}.xlsx"
            if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                print_log(f"  Tramo {i}/{len(chunks)}: {chunk_path} ya existe de un intento anterior, se omite.")
                continue

            await load_wo_management()
            chunk_range_str = format_date_range(chunk_start, chunk_end)
            print_log(f"  Tramo {i}/{len(chunks)}: '{chunk_range_str}' -> {chunk_path}")
            for chunk_attempt in range(1, 3):
                try:
                    await run_search_and_export(
                        page, ["Closed", "Closed FT"], chunk_range_str, chunk_path,
                        overlay_timeout=180000, download_timeout=300000
                    )
                    break
                except Exception as e:
                    print_log(f"  [Tramo {i}] Intento {chunk_attempt} falló: {e}")
                    if chunk_attempt == 2:
                        raise
                    await asyncio.sleep(5)
                    await load_wo_management()

        await browser.close()
        print_log("Proceso finalizado.")

async def async_main():
    if not USER or not PASSWORD or not LOGIN_URL:
        print_log("Error: Por favor verifique sus credenciales en el archivo .env")
        raise ValueError("Credenciales incompletas en el archivo .env")

    for old_chunk in glob.glob("./reporte_gnoc_closed_*.xlsx"):
        try:
            os.remove(old_chunk)
        except Exception:
            pass

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        print_log(f"Iniciando intento {attempt} de {max_attempts} del flujo completo de descarga...")
        try:
            await run_flow()
            print_log("¡Descarga de reporte finalizada con éxito!")
            break
        except Exception as e:
            print_log(f"Intento {attempt} falló con error: {e}")
            if attempt < max_attempts:
                print_log("Esperando 20 segundos de cooldown antes de reintentar...")
                await asyncio.sleep(20)
            else:
                print_log("Se agotaron todos los intentos de descarga del reporte.")
                raise Exception(f"No se pudo descargar el reporte de GNOC tras {max_attempts} intentos. Último error: {e}")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
