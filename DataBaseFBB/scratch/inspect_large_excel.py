import os
import pandas as pd

def inspect_large():
    path = r"c:\Users\jjvar\OneDrive\BITEL\STATUS ENE-ABR WO.xlsx"
    if not os.path.exists(path):
        print("File not found.")
        return
        
    print(f"Inspecting large Excel file: {path}")
    xl = pd.ExcelFile(path)
    
    target_sheets = ['GNOC', 'Data']
    for sheet in target_sheets:
        if sheet in xl.sheet_names:
            print(f"\nSheet '{sheet}':")
            try:
                # Load the full sheet
                df = pd.read_excel(path, sheet_name=sheet)
                print(f"  Total rows: {len(df)}")
                print(f"  Columns: {list(df.columns)}")
                
                # Find status column
                wo_status_cols = [c for c in df.columns if 'wo' in c.lower() and 'status' in c.lower()]
                ft_cols = [c for c in df.columns if c.strip().lower() == 'ft']
                
                if wo_status_cols:
                    status_col = wo_status_cols[0]
                    print(f"  Found status column: '{status_col}'")
                    print("  Value counts for status:")
                    print(df[status_col].value_counts(dropna=False).head(5))
                    
                    ft_inproc = df[df[status_col] == 'FT Inprocessing']
                    print(f"  Total FT Inprocessing: {len(ft_inproc)}")
                    
                    if ft_cols:
                        ft_col = ft_cols[0]
                        ft_inproc_excl = ft_inproc[ft_inproc[ft_col] != 'vtp_marlo.delacruz']
                        print(f"  Total FT Inprocessing (excl. marlo.delacruz): {len(ft_inproc_excl)}")
            except Exception as e:
                print(f"  Error reading sheet '{sheet}': {e}")

if __name__ == '__main__':
    inspect_large()
