import os
import glob
import pandas as pd

def check_excels():
    excel_dir = 'Reporte FTTH'
    files = glob.glob(os.path.join(excel_dir, 'Reporte_Ops_*.xlsx'))
    if not files:
        print("No Excel files found.")
        return
        
    # Sort files by name/date to get the most recent one
    files.sort()
    print("Found Excel files:")
    for f in files:
        print(f" - {f} ({os.path.getsize(f) / 1024 / 1024:.2f} MB)")
        
    latest_file = files[-1]
    print(f"\nAnalyzing latest file: {latest_file}")
    
    xl = pd.ExcelFile(latest_file)
    print("Sheets in Excel file:", xl.sheet_names)
    
    # Let's read the main/first sheet or search for sheet containing 'incident' or similar
    # If there's only one sheet or standard sheets, print their info
    for sheet_name in xl.sheet_names:
        print(f"\nReading sheet: '{sheet_name}'")
        try:
            df = pd.read_excel(latest_file, sheet_name=sheet_name)
            print(f"  Rows: {len(df)}, Columns: {list(df.columns)}")
            
            # Check for WO Status column
            wo_status_col = [c for c in df.columns if 'wo' in c.lower() and 'status' in c.lower()]
            ft_col = [c for c in df.columns if c.strip().lower() == 'ft']
            
            if wo_status_col:
                col_name = wo_status_col[0]
                print(f"  Value counts for '{col_name}':")
                print(df[col_name].value_counts(dropna=False).head(5))
                
                if ft_col:
                    ft_col_name = ft_col[0]
                    # Filter for FT Inprocessing
                    ft_inproc = df[df[col_name] == 'FT Inprocessing']
                    print(f"  Total FT Inprocessing in Excel sheet: {len(ft_inproc)}")
                    
                    # Exclude vtp_marlo.delacruz
                    ft_inproc_excl = ft_inproc[ft_inproc[ft_col_name] != 'vtp_marlo.delacruz']
                    print(f"  Total FT Inprocessing (excl. marlo.delacruz) in Excel sheet: {len(ft_inproc_excl)}")
                    
                    # If we check the date column, let's see when they start
                    # Look for create date or date column
                    date_col = [c for c in df.columns if 'create' in c.lower() or 'fecha' in c.lower()]
                    if date_col:
                        d_col = date_col[0]
                        print(f"  Date column: {d_col}")
                        # Check min/max dates
                        print(f"  Min date: {df[d_col].min()}, Max date: {df[d_col].max()}")
        except Exception as e:
            print(f"  Error reading sheet '{sheet_name}': {e}")

if __name__ == '__main__':
    check_excels()
