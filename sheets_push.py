"""
sheets_push.py — Reemplaza el paso manual de "borrar y pegar en Google Sheets" (antes hecho
a mano vía Claude in Chrome) por la API oficial de Google Sheets, para poder correr sin
supervisión dentro del sync automático (ver run_full_sync.py).

Exporta las WOs pendientes sin error (mismo filtro que /api/work_orders/export?type=valid
en server.py) y reemplaza el rango F2:U<n> de la pestaña "template realease lvl 3" en la
hoja "INCIDENTS PARTNERS", igual que el proceso manual: limpia el rango completo primero
(para no dejar filas viejas residuales si la nueva tanda es más corta) y luego escribe los
datos nuevos desde F2 hacia abajo/derecha, sin encabezados.

Las 16 columnas (F..U) son, en orden: BRANCH, WO_CODE, TICKET_CODE, WO_CREATE_DATE,
RESPONSIBLE_UNIT_WO, FT Reassigned, ISDN/Account, Warranty Days, Implementation test,
Act Status, Sub Status, Online Status, Ft Code, Staf Team, Connector_Code, COMPCONTENT.
"""
import os
import json
import sqlite3
import calendar
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_PATH, "gnoc.db")

SPREADSHEET_ID = "1U3tzOPUnUU3RJJw_qBsaqEr-_TeNCALM9vJmvG2WdZI"
SHEET_TAB_NAME = "template realease lvl 3"
PASTE_START_ROW = 2
PASTE_START_COL = "F"
PASTE_END_COL = "U"
# Techo generoso de filas a limpiar antes de pegar, para borrar cualquier residuo de una
# tanda anterior más larga sin tener que leer primero cuántas filas había.
CLEAR_END_ROW = 5000

ERRORS_TAB_NAME = "ERRORES LVL3"
GNOCALL_TAB_NAME = "GNOCALL"
GNOCALL_START_ROW = 2
# Techo generoso propio de GNOCALL -la hoja ya tenía ~25000 filas de antes, muy por encima
# del CLEAR_END_ROW de 5000 que usa "template realease lvl 3" (que sí cabe en ese tamaño).
GNOCALL_CLEAR_END_ROW = 40000

# Mismo archivo que persiste server.py (save_sync_month_range) con el rango de meses elegido
# en el dashboard -se lee tal cual en vez de importar server.py para evitar un import
# circular (server.py ya importa este módulo).
SYNC_MONTH_RANGE_PATH = os.path.join(BASE_PATH, "sync_month_range.json")
# Mismo default que GNOC_LOOKBACK_DAYS en download_report.py, para replicar la misma
# ventana móvil cuando no se eligió un rango explícito ("Automático").
GNOC_LOOKBACK_DAYS = int(os.environ.get("GNOC_LOOKBACK_DAYS", "60"))

SERVICE_ACCOUNT_JSON = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    os.path.join(BASE_PATH, "google_service_account.json")
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

QUERY = """
    SELECT branch, wo_code, ticket_code, wo_create_date, responsible_unit,
           ft_technician, account, warranty_period, implementation_test,
           act_status, sub_status, online_status, ft_gnoc, staf_team,
           connector_code, compcontent
    FROM work_orders
    WHERE is_error = 0 AND LOWER(wo_status) NOT IN ('close', 'closed', 'closed ft', 'ft completed')
    ORDER BY pending_hours DESC
"""


def _clean(value):
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()


def fetch_pending_valid_rows():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute(QUERY)
    rows = [[_clean(v) for v in row] for row in cursor.fetchall()]
    conn.close()
    return rows


def push_pending_valid_to_sheet():
    if not os.path.exists(SERVICE_ACCOUNT_JSON):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales de la cuenta de servicio "
            f"'{SERVICE_ACCOUNT_JSON}'. Configura GOOGLE_SERVICE_ACCOUNT_JSON en .env o "
            f"coloca el JSON con ese nombre en la raíz del proyecto."
        )

    rows = fetch_pending_valid_rows()
    print(f"[Sheets] {len(rows)} WOs pendientes sin error a publicar.", flush=True)

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(SHEET_TAB_NAME)

    clear_range = f"{PASTE_START_COL}{PASTE_START_ROW}:{PASTE_END_COL}{CLEAR_END_ROW}"
    ws.batch_clear([clear_range])
    print(f"[Sheets] Rango {clear_range} limpiado.", flush=True)

    if rows:
        end_row = PASTE_START_ROW + len(rows) - 1
        paste_range = f"{PASTE_START_COL}{PASTE_START_ROW}:{PASTE_END_COL}{end_row}"
        ws.update(range_name=paste_range, values=rows, value_input_option="USER_ENTERED")
        print(f"[Sheets] {len(rows)} filas pegadas en {paste_range}.", flush=True)

    return len(rows)


def fetch_marlo_error_rows():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT wo_code, ticket_code FROM work_orders WHERE is_error = 1")
    rows = [(_clean(wo), _clean(tt)) for wo, tt in cursor.fetchall()]
    conn.close()
    return rows


def _format_create_time(value):
    """create_time en la DB queda como 'YYYY-MM-DD HH:MM:SS' (ver process_data.py); la
    pestaña GNOCALL ya viene con el formato 'DD/MM/YYYY HH:MM:SS' de GNOC, así que se
    reconvierte para que las filas nuevas se vean igual que las que ya había."""
    value = _clean(value)
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return value


def _get_synced_date_range():
    """Replica la ventana de fechas que download_report.py acaba de usar para bajar GNOC:
    el rango de meses elegido en el dashboard (persistido por server.py en
    sync_month_range.json) si hay uno, o si no la misma ventana móvil de GNOC_LOOKBACK_DAYS
    días que usa por defecto ("Automático")."""
    if os.path.exists(SYNC_MONTH_RANGE_PATH):
        try:
            with open(SYNC_MONTH_RANGE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            from_month, to_month = data.get("from_month"), data.get("to_month")
            if from_month and to_month:
                start_dt = datetime.strptime(from_month, "%Y-%m")
                end_first = datetime.strptime(to_month, "%Y-%m")
                last_day = calendar.monthrange(end_first.year, end_first.month)[1]
                end_dt = end_first.replace(day=last_day, hour=23, minute=59, second=59)
                return start_dt, end_dt
        except (ValueError, OSError):
            pass
    end_dt = datetime.now().replace(hour=23, minute=59, second=59)
    start_dt = (datetime.now() - timedelta(days=GNOC_LOOKBACK_DAYS)).replace(hour=0, minute=0, second=0)
    return start_dt, end_dt


def fetch_wo_rows_in_range(start_dt, end_dt):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT wo_code, create_time, account, ft_comment
        FROM work_orders
        WHERE create_time BETWEEN ? AND ?
        ORDER BY create_time ASC
        """,
        (start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")),
    )
    rows = [
        (_clean(wo_code), _format_create_time(create_time), _clean(account), _clean(ft_comment))
        for wo_code, create_time, account, ft_comment in cursor.fetchall()
    ]
    conn.close()
    return rows


def push_gnocall_to_sheet():
    """Reemplaza en la pestaña "GNOCALL" (A=WO code, B=Create Time, C=Subscribers, E=FT
    comment) los datos del período de meses recién sincronizado -abiertas y cerradas por
    igual, sin el filtro de is_error que sí aplica push_pending_valid_to_sheet(). A
    diferencia de ERRORES LVL3, esto SÍ limpia el rango antes de escribir (igual que
    push_pending_valid_to_sheet), porque cada sync debe reflejar exactamente el período
    recién descargado, no ir acumulando duplicados. Nunca toca D ('Recurring in last 30
    days') ni F ('Avería'), que se llenan aparte."""
    if not os.path.exists(SERVICE_ACCOUNT_JSON):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales de la cuenta de servicio "
            f"'{SERVICE_ACCOUNT_JSON}'. Configura GOOGLE_SERVICE_ACCOUNT_JSON en .env o "
            f"coloca el JSON con ese nombre en la raíz del proyecto."
        )

    start_dt, end_dt = _get_synced_date_range()
    rows = fetch_wo_rows_in_range(start_dt, end_dt)
    print(f"[Sheets] {len(rows)} WOs entre {start_dt} y {end_dt} a publicar en GNOCALL.", flush=True)

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(GNOCALL_TAB_NAME)

    clear_range_abc = f"A{GNOCALL_START_ROW}:C{GNOCALL_CLEAR_END_ROW}"
    clear_range_e = f"E{GNOCALL_START_ROW}:E{GNOCALL_CLEAR_END_ROW}"
    ws.batch_clear([clear_range_abc, clear_range_e])
    print(f"[Sheets] Rangos {clear_range_abc} y {clear_range_e} limpiados.", flush=True)

    if rows:
        abc_rows = [[r[0], r[1], r[2]] for r in rows]
        e_rows = [[r[3]] for r in rows]
        end_row = GNOCALL_START_ROW + len(rows) - 1
        ws.update(range_name=f"A{GNOCALL_START_ROW}:C{end_row}", values=abc_rows, value_input_option="USER_ENTERED")
        ws.update(range_name=f"E{GNOCALL_START_ROW}:E{end_row}", values=e_rows, value_input_option="USER_ENTERED")
        print(f"[Sheets] {len(rows)} filas escritas en GNOCALL (filas {GNOCALL_START_ROW}-{end_row}).", flush=True)

    return len(rows)


def push_marlo_errors_to_sheet():
    """Agrega en la pestaña "ERRORES LVL3" (columnas A=WO_CODE, B=TT_CODE) las WOs marcadas
    como error de la cuenta de Marlo (vtp_marlo.delacruz) que todavía no estén registradas
    ahí. A diferencia de push_pending_valid_to_sheet(), esto NUNCA limpia el rango -- solo
    agrega filas nuevas al final de lo que ya hay, para no perder el historial acumulado."""
    if not os.path.exists(SERVICE_ACCOUNT_JSON):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales de la cuenta de servicio "
            f"'{SERVICE_ACCOUNT_JSON}'. Configura GOOGLE_SERVICE_ACCOUNT_JSON en .env o "
            f"coloca el JSON con ese nombre en la raíz del proyecto."
        )

    db_rows = fetch_marlo_error_rows()

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(ERRORS_TAB_NAME)

    existing_codes = set(ws.col_values(1))
    seen = set()
    new_rows = []
    for wo_code, ticket_code in db_rows:
        if wo_code and wo_code not in existing_codes and wo_code not in seen:
            new_rows.append([wo_code, ticket_code])
            seen.add(wo_code)

    if not new_rows:
        print("[Sheets] Sin errores nuevos de Marlo por agregar en ERRORES LVL3.", flush=True)
        return 0

    start_row = len(ws.col_values(1)) + 1
    end_row = start_row + len(new_rows) - 1
    paste_range = f"A{start_row}:B{end_row}"
    ws.update(range_name=paste_range, values=new_rows, value_input_option="USER_ENTERED")
    print(f"[Sheets] {len(new_rows)} errores nuevos de Marlo agregados en {paste_range}.", flush=True)

    return len(new_rows)


if __name__ == "__main__":
    push_pending_valid_to_sheet()
    push_marlo_errors_to_sheet()
    push_gnocall_to_sheet()
