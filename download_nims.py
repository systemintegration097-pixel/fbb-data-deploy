import os
import sys
import glob
import asyncio
import sqlite3
import openpyxl
from datetime import datetime
from html.parser import HTMLParser
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(override=True)

script_dir = os.path.dirname(os.path.abspath(__file__))
NIMS_DIR = os.path.join(script_dir, "NIMS")
TMS_DIR = os.path.join(script_dir, "TMs")
DB_PATH = os.path.join(script_dir, "gnoc.db")

# Portal TMs (TM.s Technical Management Supporter) - descarga el radaccount fresco antes de
# procesarlo, en vez de depender de que alguien lo baje a mano y lo deje en la carpeta TMs/.
TMS_LOGIN_URL = os.getenv("TMS_LOGIN_URL", "http://10.121.62.102:8080/backup/?target=error&err=denied")
TMS_USER = os.getenv("TMS_USER")
TMS_PASSWORD = os.getenv("TMS_PASSWORD")
TMS_ZONE_VALUE = os.getenv("TMS_ZONE_VALUE", "10.121.62.167")  # "VTP" en el selector de Zone
TMS_FILTER_ACCOUNT = os.getenv("TMS_FILTER_ACCOUNT", "gftth")

# Portal NIMS (Bitel Passport - Quan ly thue bao > Bao cao thue bao bang rong co dinh) -
# mismo motivo que TMs: descargar el reporte fresco en vez de depender de que alguien lo
# baje a mano y lo deje en la carpeta NIMS/.
NIMS_LOGIN_URL = os.getenv("NIMS_LOGIN_URL", "http://10.121.13.152:9009/NIMS/Index.do?request_locale=vi_VN")
NIMS_USER = os.getenv("NIMS_USER")
NIMS_PASSWORD = os.getenv("NIMS_PASSWORD")

# El portal NIMS bloquea la cuenta tras 5 logins fallidos por día. Cuando este script corre
# desatendido varias veces al día (ver run_full_sync.py), un problema persistente (credencial
# vencida, portal caído) podría acumular fallos rápido y quemar el cupo antes de que alguien
# se entere. Este archivo de estado cuenta los fallos del día; al llegar a NIMS_LOGIN_FAILURE_LIMIT
# se deja de intentar el login por el resto del día (se sigue usando el último Excel NIMS en disco).
NIMS_LOGIN_STATE_FILE = os.path.join(script_dir, "nims_login_state.json")
NIMS_LOGIN_FAILURE_LIMIT = 2

sys.stdout.reconfigure(encoding='utf-8')

def _load_nims_login_state():
    import json
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(NIMS_LOGIN_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        if state.get("date") != today:
            return {"date": today, "failures": 0}
        return state
    except Exception:
        return {"date": today, "failures": 0}

def _save_nims_login_state(state):
    import json
    try:
        with open(NIMS_LOGIN_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        print_log(f"[Aviso] No se pudo guardar el estado de intentos de login NIMS: {e}")

def _record_nims_login_failure():
    state = _load_nims_login_state()
    state["failures"] = state.get("failures", 0) + 1
    _save_nims_login_state(state)
    return state["failures"]

def _record_nims_login_success():
    today = datetime.now().strftime("%Y-%m-%d")
    _save_nims_login_state({"date": today, "failures": 0})

def _nims_login_blocked_today():
    state = _load_nims_login_state()
    return state.get("failures", 0) >= NIMS_LOGIN_FAILURE_LIMIT

def print_log(msg):
    print(msg, flush=True)

class TMHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = []
        self.current_cell = []
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_cell = True
            self.current_cell = []
        elif tag == 'tr':
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_cell = False
            self.current_row.append(''.join(self.current_cell).strip())
        elif tag == 'tr':
            if self.current_row:
                self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)

def get_newest_file(directory, extensions):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        return None
    files = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if any(f.endswith(ext) for ext in extensions)
    ]
    if not files:
        return None
    # Order by modification time descending
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def import_nims():
    print_log(f"Buscando archivo de NIMS en {NIMS_DIR}...")
    newest_nims = get_newest_file(NIMS_DIR, [".xlsx"])
    if not newest_nims:
        print_log("[ADVERTENCIA] No se encontró ningún archivo .xlsx en la carpeta NIMS. Se omite importación de NIMS.")
        return False
        
    print_log(f"Importando archivo NIMS más reciente: {newest_nims}")
    wb = openpyxl.load_workbook(newest_nims, read_only=True)
    sheet = wb.active
    sheet.reset_dimensions()
    
    data_rows = []
    for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if r_idx < 8:  # Saltar cabeceras
            continue
        if not row or row[0] is None or str(row[0]).strip() == '' or str(row[0]).strip() == 'STT':
            continue
            
        def safe_str(val):
            return str(val).strip() if val is not None else ""
            
        mapped_row = [
            safe_str(row[0]),  # stt
            safe_str(row[4]),  # unit_name
            safe_str(row[18]), # unit_code
            safe_str(row[12]), # province
            safe_str(row[12]), # district
            safe_str(row[5]),  # site_code
            safe_str(row[5]),  # site_id
            safe_str(row[5]),  # site_name
            safe_str(row[8]),  # box_code
            safe_str(row[9]),  # connector_code
            safe_str(row[1]),  # account
            safe_str(row[13]), # contract_code
            safe_str(row[3]),  # service_type
            safe_str(row[17]), # customer_name
            safe_str(row[16]), # phone
            'Active',          # status (por defecto Active, luego actualizado con TMs)
            safe_str(row[22]), # connection_date
            safe_str(row[15])  # address
        ]
        data_rows.append(mapped_row)
        
    wb.close()
    print_log(f"Total de registros NIMS procesados: {len(data_rows)}")
    
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    
    print_log("Limpiando tabla 'nims_subscribers' e insertando nuevos registros...")
    cursor.execute("DELETE FROM nims_subscribers")
    cursor.executemany("""
        INSERT INTO nims_subscribers (
            stt, unit_name, unit_code, province, district,
            site_code, site_id, site_name, box_code, connector_code,
            account, contract_code, service_type, customer_name, phone,
            status, connection_date, address
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_rows)
    
    conn.commit()
    conn.close()
    print_log("¡Importación de NIMS completada con éxito!")
    return True

def import_tms():
    print_log(f"Buscando archivo de TMs en {TMS_DIR}...")
    newest_tm = get_newest_file(TMS_DIR, [".xls"])
    if not newest_tm:
        print_log("[ADVERTENCIA] No se encontró ningún archivo .xls en la carpeta TMs. Se omite importación de TMs.")
        return False
        
    print_log(f"Importando archivo TMs (radaccount) más reciente: {newest_tm}")
    
    parser = TMHtmlParser()
    with open(newest_tm, "r", encoding="utf-8", errors="ignore") as f:
        parser.feed(f.read())
        
    rows = parser.rows
    if not rows:
        print_log("[ERROR] El archivo de TMs no contiene filas válidas.")
        return False
        
    # La primera fila debe ser la cabecera
    header = [col.upper() for col in rows[0]]
    
    # Crear un mapeo dinámico para mayor seguridad
    col_map = {col: idx for idx, col in enumerate(header)}
    
    print_log(f"Filas leídas de TMs: {len(rows) - 1}")
    
    data_rows = []
    for r in rows[1:]:
        if len(r) < len(header):
            continue
            
        def get_val(col_name):
            idx = col_map.get(col_name)
            return r[idx].strip() if idx is not None and idx < len(r) else ""
            
        data_rows.append((
            get_val('ID'),
            get_val('USERNAME'),
            get_val('MAC'),
            get_val('PORT'),
            get_val('STATUS'),
            get_val('SET'),
            get_val('ACTIVEDATE'),
            get_val('CANCELDATE'),
            get_val('SUSPENDDATE'),
            get_val('REACTIVEDATE'),
            get_val('BRAS'),
            get_val('PORTCHANGEDATE'),
            get_val('GROUPNAME'),
            get_val('IPADDRESS')
        ))
        
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    
    print_log("Limpiando tabla 'tm_subscribers' e insertando nuevos registros...")
    cursor.execute("DELETE FROM tm_subscribers")
    cursor.executemany("""
        INSERT INTO tm_subscribers (
            id, username, mac, port, status, "set", activedate, canceldate,
            suspenddate, reactivedate, bras, portchangedate, groupname, ipaddress
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_rows)
    
    conn.commit()
    conn.close()
    print_log("¡Importación de TMs completada con éxito!")
    return True

def apply_status_rules():
    print_log("Aplicando reglas de negocio cruzando NIMS y TMs en SQLite...")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    
    # 1. Marcar clientes en TMs con su estado correspondiente (0 -> Activo, 2 -> Suspendido)
    print_log("  Actualizando estados para clientes que existen en TMs...")
    cursor.execute("""
        UPDATE nims_subscribers
        SET status = (
            SELECT CASE 
                WHEN tm.status = '0' THEN 'Activo'
                WHEN tm.status = '2' THEN 'Suspendido'
                ELSE 'Status ' || tm.status
            END
            FROM tm_subscribers tm
            WHERE tm.username = nims_subscribers.account
        )
        WHERE EXISTS (
            SELECT 1 FROM tm_subscribers tm WHERE tm.username = nims_subscribers.account
        )
    """)
    updated_tm = cursor.rowcount
    print_log(f"  Estados actualizados desde TMs: {updated_tm}")
    
    # 2. Marcar clientes que están en NIMS pero no en TMs como 'Cancelado'
    print_log("  Marcando clientes ausentes de TMs como 'Cancelado'...")
    cursor.execute("""
        UPDATE nims_subscribers
        SET status = 'Cancelado'
        WHERE NOT EXISTS (
            SELECT 1 FROM tm_subscribers tm WHERE tm.username = nims_subscribers.account
        )
    """)
    updated_cancelled = cursor.rowcount
    print_log(f"  Clientes marcados como 'Cancelado': {updated_cancelled}")
    
    conn.commit()
    conn.close()
    print_log("¡Reglas de estados aplicadas con éxito!")

async def download_tms_file():
    """Descarga un radaccount fresco del portal TMs (Internet Service > FTTH Service >
    Account on AAA, Zone=VTP, Account=gftth > Export) y reemplaza los archivos viejos en TMs/.
    El archivo que exporta el portal es HTML disfrazado de .xls (por eso TMHtmlParser lo lee
    como HTML, no como Excel real) - confirmado navegando el portal en vivo el 2026-08-06."""
    if not TMS_USER or not TMS_PASSWORD:
        print_log("[Aviso] TMS_USER/TMS_PASSWORD no configurados en .env; se omite la descarga "
                   "automática de TMs y se usa el archivo más reciente que ya exista en TMs/.")
        return False

    os.makedirs(TMS_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.on("pageerror", lambda err: print_log(f"[TMS BROWSER PAGE ERROR] {err}"))

        try:
            print_log(f"Navegando al portal TMs: {TMS_LOGIN_URL}")
            await page.goto(TMS_LOGIN_URL, timeout=45000)
            await asyncio.sleep(2)

            login_link = page.locator("a", has_text="Log in")
            if await login_link.count() > 0:
                await login_link.first.click()
                await asyncio.sleep(2)

            login_ok = False
            for attempt in range(1, 3):
                if await page.locator("input[name='username']").count() == 0:
                    login_ok = True
                    break
                print_log(f"  Intento {attempt}/2 de login TMs...")
                await page.fill("input[name='username']", TMS_USER)
                await page.fill("input[name='pwd']", TMS_PASSWORD)
                try:
                    # El clic puede quedar esperando "scheduled navigations to finish" y tirar
                    # TimeoutError sin que eso signifique que el login falló -el chequeo real
                    # ocurre abajo-, así que no debe abortar el bucle de reintentos (mismo
                    # problema confirmado en CNOC, aplicado acá de forma preventiva).
                    await page.locator("input[name='b_login']").click(timeout=15000)
                except Exception as e:
                    print_log(f"  [Aviso] El clic en 'Login' tardó de más ({e}); verificando igual si la sesión avanzó...")
                await asyncio.sleep(3)
                if await page.locator("input[name='username']").count() == 0:
                    login_ok = True
                    break

            if not login_ok:
                await page.screenshot(path="./screenshot_tms_login_error.png")
                await browser.close()
                raise Exception(
                    "No se pudo iniciar sesión en el portal TMs. Es probable que la contraseña "
                    "de TMs (TMS_USER/TMS_PASSWORD en .env) sea incorrecta y deba actualizarse "
                    "(sección Credenciales)."
                )
            print_log("Login TMs exitoso.")

            print_log("Navegando a Internet Service > FTTH Service > Account on AAA...")
            await page.locator("button.bmenu", has_text="Internet Service").first.click()
            await asyncio.sleep(1)
            await page.locator(".x-menu-item", has_text="FTTH Service").first.hover()
            await asyncio.sleep(1)
            await page.locator(".x-menu-item", has_text="Account on AAA").first.click()
            await asyncio.sleep(3)

            await page.wait_for_selector("select[name='search[aaaserver]']", timeout=20000)
            print_log(f"Configurando Zone={TMS_ZONE_VALUE!r} y Account={TMS_FILTER_ACCOUNT!r}...")
            await page.select_option("select[name='search[aaaserver]']", TMS_ZONE_VALUE)
            await page.fill("input[name='search[accname]']", TMS_FILTER_ACCOUNT)

            print_log("Haciendo clic en 'Search'...")
            await page.locator("input[name='b_search']").click()
            await asyncio.sleep(4)

            # El portal comparte la misma plantilla/arquitectura que GNOC y CNOC, donde el botón
            # de exportar a veces falla ("Export fail") y solo hay que reintentar el clic -por
            # eso se reintenta varias veces con espera corta en vez de un timeout largo único.
            print_log("Iniciando descarga haciendo clic en 'Export'...")
            export_click_retries = 6
            export_click_timeout = 45000
            download = None
            last_error = None
            for click_attempt in range(1, export_click_retries + 1):
                try:
                    async with page.expect_download(timeout=export_click_timeout) as download_info:
                        await page.locator("input[name='b_export']").click()
                    download = await download_info.value
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    print_log(f"  [Intento {click_attempt}/{export_click_retries}] El clic en 'Export' no generó descarga, reintentando...")
                    await asyncio.sleep(2)

            if last_error:
                await page.screenshot(path="./screenshot_tms_export_error.png")
                await browser.close()
                raise last_error

            # Reemplazar archivos viejos: mismo criterio que GNOC (borrar antes de guardar el
            # nuevo, para no ir acumulando archivos de ~20MB en una carpeta sincronizada a OneDrive).
            for old_file in glob.glob(os.path.join(TMS_DIR, "radaccount*.xls")):
                try:
                    os.remove(old_file)
                except Exception as e:
                    print_log(f"  [Aviso] No se pudo borrar {old_file}: {e}")

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            save_path = os.path.join(TMS_DIR, f"radaccount{timestamp}.xls")
            await download.save_as(save_path)
            print_log(f"[ÉXITO] TMs descargado en: {save_path} ({os.path.getsize(save_path)} bytes)")

            await browser.close()
            return True

        except Exception as e:
            print_log(f"Error durante la descarga de TMs: {e}")
            try:
                await browser.close()
            except Exception:
                pass
            raise

async def download_nims_file():
    """Descarga un reporte fresco del portal NIMS (Quản lý thuê bao > Báo cáo thuê bao
    băng rộng cố định > Tìm kiếm > Export) y reemplaza los archivos viejos en NIMS/.
    Este reporte trae el 'Sub node code' (la caja) donde está cada cliente actualmente,
    que luego se cruza con la pestaña 'List of Boxes' de Tableau para saber el branch.
    El portal es un CAS ('Bitel Passport') que redirige de vuelta a la misma URL de NIMS
    tras loguear -no cambia de URL-, así que el login se verifica comprobando que el
    campo #username ya no está presente. El portal avisa que bloquea la cuenta tras 5
    intentos fallidos por día, así que -a diferencia de otros portales- NO se reintenta
    el login automáticamente: si falla, se corta ahí mismo con un mensaje claro."""
    if not NIMS_USER or not NIMS_PASSWORD:
        print_log("[Aviso] NIMS_USER/NIMS_PASSWORD no configurados en .env; se omite la "
                   "descarga automática de NIMS y se usa el archivo más reciente que ya "
                   "exista en NIMS/.")
        return False

    os.makedirs(NIMS_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1600, "height": 1000},
            accept_downloads=True,
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.on("pageerror", lambda err: print_log(f"[NIMS BROWSER PAGE ERROR] {err}"))

        try:
            print_log(f"Navegando al portal NIMS: {NIMS_LOGIN_URL}")
            await page.goto(NIMS_LOGIN_URL, timeout=45000)
            await asyncio.sleep(2)

            if await page.locator("#username").count() > 0:
                print_log("Ingresando credenciales de NIMS...")
                await page.fill("#username", NIMS_USER)
                await page.fill("#password", NIMS_PASSWORD)
                await page.click("input[name='submit']")
                await asyncio.sleep(4)

            if await page.locator("#username").count() > 0:
                await page.screenshot(path="./screenshot_nims_login_error.png")
                await browser.close()
                failures_today = _record_nims_login_failure()
                raise Exception(
                    "No se pudo iniciar sesión en el portal NIMS (el formulario de login sigue "
                    "visible). La cuenta se bloquea tras 5 intentos fallidos por día, así que no "
                    "se reintenta automáticamente: verificar NIMS_USER/NIMS_PASSWORD en la "
                    f"sección Credenciales antes de volver a intentar. (Fallos de login hoy: {failures_today})"
                )
            _record_nims_login_success()
            print_log("Login NIMS exitoso.")

            print_log("Navegando a Quản lý thuê bao > Báo cáo thuê bao băng rộng cố định...")
            await page.locator("text=Quản lý thuê bao").first.hover()
            await asyncio.sleep(1)
            await page.locator("text=Báo cáo thuê bao băng rộng cố định").first.click()
            await asyncio.sleep(4)

            # El formulario y los botones viven dentro de un iframe interno del portal.
            report_frame = None
            for fr in page.frames:
                try:
                    if await fr.locator("text=Tìm kiếm").count() > 0:
                        report_frame = fr
                        break
                except Exception:
                    continue
            if report_frame is None:
                await page.screenshot(path="./screenshot_nims_frame_error.png")
                await browser.close()
                raise Exception("No se encontró el formulario de 'Báo cáo thuê bao băng rộng cố định' (iframe no localizado).")

            print_log("Haciendo clic en 'Tìm kiếm' (sin filtros, trae todos los clientes activados)...")
            await report_frame.locator("text=Tìm kiếm").first.click()
            await asyncio.sleep(5)

            # El reporte trae ~150 mil filas, así que la generación del Excel de exportación
            # puede tardar; se reintenta el clic con timeouts generosos por si el primer
            # intento no dispara la descarga (mismo patrón ya visto en GNOC/CNOC/TMs).
            print_log("Iniciando descarga haciendo clic en 'Export' (puede tardar varios minutos)...")
            export_click_retries = 3
            export_click_timeout = 180000
            download = None
            last_error = None
            for click_attempt in range(1, export_click_retries + 1):
                try:
                    async with page.expect_download(timeout=export_click_timeout) as download_info:
                        await report_frame.locator("text=Export").first.click()
                    download = await download_info.value
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    print_log(f"  [Intento {click_attempt}/{export_click_retries}] El clic en 'Export' no generó descarga, reintentando...")
                    await asyncio.sleep(3)

            if last_error:
                await page.screenshot(path="./screenshot_nims_export_error.png")
                await browser.close()
                raise last_error

            # Reemplazar archivos viejos: mismo criterio que TMs/GNOC (borrar antes de
            # guardar el nuevo para no acumular archivos de ~25-30MB en una carpeta
            # sincronizada a OneDrive). El portal ya nombra el archivo de forma única
            # (fecha + timestamp), así que se conserva ese nombre tal cual.
            for old_file in glob.glob(os.path.join(NIMS_DIR, "*ReportSubGpon*.xlsx")):
                try:
                    os.remove(old_file)
                except Exception as e:
                    print_log(f"  [Aviso] No se pudo borrar {old_file}: {e}")

            filename = download.suggested_filename or f"ReportSubGpon_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
            save_path = os.path.join(NIMS_DIR, filename)
            await download.save_as(save_path)
            print_log(f"[ÉXITO] NIMS descargado en: {save_path} ({os.path.getsize(save_path)} bytes)")

            await browser.close()
            return True

        except Exception as e:
            print_log(f"Error durante la descarga de NIMS: {e}")
            try:
                await browser.close()
            except Exception:
                pass
            raise

def main():
    print_log("Iniciando sincronización de NIMS y TMs...")

    if _nims_login_blocked_today():
        print_log(f"[Aviso] Se alcanzó el límite de {NIMS_LOGIN_FAILURE_LIMIT} intentos de login "
                   f"NIMS fallidos hoy; se omite el intento (para no arriesgar el bloqueo de la "
                   f"cuenta a 5 fallos/día) y se usa el archivo NIMS existente más reciente.")
    else:
        try:
            asyncio.run(download_nims_file())
        except Exception as e:
            # No fatal: si la descarga falla, se sigue con el archivo NIMS más reciente que ya
            # exista en disco (de una corrida anterior) en vez de abortar todo el sync.
            print_log(f"[Aviso] Descarga automática de NIMS falló, se usará el archivo existente más reciente si lo hay: {e}")

    try:
        asyncio.run(download_tms_file())
    except Exception as e:
        # No fatal: si la descarga falla, se sigue con el archivo TMs más reciente que ya
        # exista en disco (de una corrida anterior) en vez de abortar todo el sync.
        print_log(f"[Aviso] Descarga automática de TMs falló, se usará el archivo existente más reciente si lo hay: {e}")

    nims_ok = import_nims()
    tm_ok = import_tms()

    if nims_ok or tm_ok:
        apply_status_rules()
        print_log("Sincronización de datos locales completada.")
        return True
    else:
        print_log("No se importó ningún dato nuevo.")
        return False

if __name__ == "__main__":
    main()
