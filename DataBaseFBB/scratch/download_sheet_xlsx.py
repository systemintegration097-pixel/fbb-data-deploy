import urllib.request
import os
import pandas as pd

def download_and_check():
    sheet_id = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    dest = "scratch/temp_sheet.xlsx"
    
    print("Downloading Google Sheet as XLSX...")
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            with open(dest, "wb") as f:
                f.write(response.read())
        print("Download complete.")
        
        # Load and print sheet names
        xl = pd.ExcelFile(dest)
        print("Sheets in Google Sheet:", xl.sheet_names)
        
        # Let's inspect each sheet
        for sheet in xl.sheet_names:
            df = pd.read_excel(dest, sheet_name=sheet)
            print(f"Sheet '{sheet}': rows = {len(df)}, columns = {list(df.columns)[:5]}...")
            
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    download_and_check()
