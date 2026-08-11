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
import sqlite3
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


if __name__ == "__main__":
    push_pending_valid_to_sheet()
