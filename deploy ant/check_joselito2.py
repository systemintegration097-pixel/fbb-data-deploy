import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')
ws = sh.worksheet('Reporte diario 1')
data = ws.get_all_values()
for i, row in enumerate(data):
    if len(row) > 4 and 'joselitoc2' in str(row[4]):
        print(f'Row {i+1}: {row[:9]}')
        try:
            print('Formula in A:', ws.acell(f'A{i+1}', value_render_option='FORMULA').value)
        except:
            pass
