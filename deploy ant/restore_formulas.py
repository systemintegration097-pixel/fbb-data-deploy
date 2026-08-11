import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')
ws = sh.worksheet('Reporte diario 1')
ws.update(values=[['=IFERROR(filter(\'WO Pendiente\'!AB:AB,\'WO Pendiente\'!D:D=E' + str(i) + '),"Cuenta cliente")'] for i in range(2, 400)], range_name='A2:A399', value_input_option='USER_ENTERED')
print("Formulas restored in Column A!")
