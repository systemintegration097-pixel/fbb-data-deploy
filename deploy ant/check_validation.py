import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')

req = {
    "includeGridData": True,
    "ranges": ["Reporte diario 1!I1:I50"]
}
res = sh.fetch_sheet_metadata(req)

found_validation = False
for sheet in res['sheets']:
    if sheet['properties']['title'] == 'Reporte diario 1':
        for i, row_data in enumerate(sheet['data'][0].get('rowData', [])):
            for cell in row_data.get('values', []):
                if cell.get('dataValidation'):
                    print(f"Row {i+1} has validation: {cell.get('dataValidation')}")
                    found_validation = True

if not found_validation:
    print("NO VALIDATION FOUND IN I1:I50")
