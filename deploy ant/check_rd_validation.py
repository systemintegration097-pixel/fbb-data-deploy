import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')

req = {
    'includeGridData': True,
    'ranges': ['Reporte diario!I1:I10', 'Reporte diario!F1:F10']
}
res = sh.fetch_sheet_metadata(req)

for sheet in res['sheets']:
    if sheet['properties']['title'] == 'Reporte diario':
        for idx, col_data in enumerate(sheet['data']):
            print(f"Data block {idx}")
            for i, row_data in enumerate(col_data.get('rowData', [])):
                for cell in row_data.get('values', []):
                    print(f"Validation: {cell.get('dataValidation')}")
