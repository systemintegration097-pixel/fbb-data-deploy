import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')

req = {
    'includeGridData': True,
    'ranges': ['Reporte diario 1!I1:I10']
}
res = sh.fetch_sheet_metadata(req)

for sheet in res['sheets']:
    if sheet['properties']['title'] == 'Reporte diario 1':
        for i, row_data in enumerate(sheet['data'][0].get('rowData', [])):
            for cell in row_data.get('values', []):
                print(f"I{i+1} Validation: {cell.get('dataValidation')}")
