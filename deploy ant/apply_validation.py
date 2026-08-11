import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')
ws = sh.worksheet('Reporte diario 1')

req = {
    'includeGridData': True,
    'ranges': ['Reporte diario 1!I1000']
}
res = sh.fetch_sheet_metadata(req)
rule = res['sheets'][0]['data'][0]['rowData'][0]['values'][0]['dataValidation']

body = {
    "requests": [
        {
            "setDataValidation": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 8,
                    "endColumnIndex": 9
                },
                "rule": rule
            }
        }
    ]
}

sh.batch_update(body)
print("Data validation successfully applied to I2:I1000!")
