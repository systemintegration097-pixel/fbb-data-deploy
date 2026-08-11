import gspread
from google.oauth2.service_account import Credentials
import glob

json_cred = glob.glob('*.json')[0]
creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')
ws_source = sh.worksheet('Reporte diario 1')
ws_dest = sh.worksheet('Reporte diario')

body = {
    "requests": [
        {
            "copyPaste": {
                "source": {
                    "sheetId": ws_source.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 5,
                    "endColumnIndex": 6
                },
                "destination": {
                    "sheetId": ws_dest.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 5,
                    "endColumnIndex": 6
                },
                "pasteType": "PASTE_DATA_VALIDATION"
            }
        },
        {
            "copyPaste": {
                "source": {
                    "sheetId": ws_source.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 5,
                    "endColumnIndex": 6
                },
                "destination": {
                    "sheetId": ws_dest.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 5,
                    "endColumnIndex": 6
                },
                "pasteType": "PASTE_FORMAT"
            }
        },
        {
            "copyPaste": {
                "source": {
                    "sheetId": ws_source.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 8,
                    "endColumnIndex": 9
                },
                "destination": {
                    "sheetId": ws_dest.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 8,
                    "endColumnIndex": 9
                },
                "pasteType": "PASTE_DATA_VALIDATION"
            }
        },
        {
            "copyPaste": {
                "source": {
                    "sheetId": ws_source.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 8,
                    "endColumnIndex": 9
                },
                "destination": {
                    "sheetId": ws_dest.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": 8,
                    "endColumnIndex": 9
                },
                "pasteType": "PASTE_FORMAT"
            }
        }
    ]
}

sh.batch_update(body)
print("Copied validation and format from Reporte diario 1 to Reporte diario!")
