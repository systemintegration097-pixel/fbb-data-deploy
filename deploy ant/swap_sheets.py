import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')

try:
    old_rd = sh.worksheet('Reporte diario')
    old_rd.update_title('Reporte diario OLD')
    print("Renamed 'Reporte diario' to 'Reporte diario OLD'")
except gspread.exceptions.WorksheetNotFound:
    print("Could not find 'Reporte diario'")

try:
    rd1 = sh.worksheet('Reporte diario 1')
    rd1.update_title('Reporte diario')
    print("Renamed 'Reporte diario 1' to 'Reporte diario'")
except gspread.exceptions.WorksheetNotFound:
    print("Could not find 'Reporte diario 1'")
