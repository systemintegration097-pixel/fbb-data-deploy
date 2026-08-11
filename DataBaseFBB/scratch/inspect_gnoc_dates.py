import pandas as pd
import os

def check_gnoc_dates():
    path = r"c:\Users\jjvar\OneDrive\BITEL\GNOC.xlsx"
    if not os.path.exists(path):
        print("File not found.")
        return
        
    print(f"Inspecting: {path}")
    df = pd.read_excel(path, sheet_name='WoList')
    print("Total rows:", len(df))
    
    # Try to find create time column
    create_col = [c for c in df.columns if 'create' in c.lower() and 'time' in c.lower()][0]
    print(f"Create Time column: '{create_col}'")
    
    df[create_col] = df[create_col].fillna('').astype(str).str.strip()
    valid_dates = df[df[create_col] != '']
    
    try:
        parsed_dates = pd.to_datetime(valid_dates[create_col], errors='coerce')
        print("Chronological Min Date:", parsed_dates.min())
        print("Chronological Max Date:", parsed_dates.max())
    except Exception as e:
        print("Error parsing dates:", e)

if __name__ == '__main__':
    check_gnoc_dates()
