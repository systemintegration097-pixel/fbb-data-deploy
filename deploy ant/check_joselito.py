import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')
ws = sh.worksheet('WO Pendiente')
data = ws.get_all_values()
for row in data:
    if len(row) > 3 and 'joselitoc2' in str(row[3]):
        print('Account:', row[3])
        print('Col B:', row[1])
        print('Col AB:', row[27] if len(row) > 27 else '')
        print('Col AC:', row[28] if len(row) > 28 else '')
