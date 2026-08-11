import os
import pandas as pd

def check_parent_excels():
    parent_dir = r"c:\Users\jjvar\OneDrive\BITEL"
    excels = [
        "STATUS ENE-ABR WO.xlsx",
        "Total de WO 18-12.xlsx",
        "PLANTILLA WO REPORT.xlsx",
        "GNOC.xlsx"
    ]
    
    for filename in excels:
        path = os.path.join(parent_dir, filename)
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue
            
        print(f"\nAnalyzing: {filename} ({os.path.getsize(path)/1024/1024:.2f} MB)")
        try:
            # First read just the columns
            xl = pd.ExcelFile(path)
            print(f"  Sheets: {xl.sheet_names}")
            
            # Let's inspect the first sheet
            sheet_name = xl.sheet_names[0]
            # Read first 100 rows to see columns
            df_sample = pd.read_excel(path, sheet_name=sheet_name, nrows=100)
            print(f"  Columns: {list(df_sample.columns)}")
            
            # Check if it has WO Status or similar
            wo_status_cols = [c for c in df_sample.columns if 'wo' in c.lower() and 'status' in c.lower()]
            ft_cols = [c for c in df_sample.columns if c.strip().lower() == 'ft']
            
            if wo_status_cols:
                status_col = wo_status_cols[0]
                print(f"  Found status column: '{status_col}'")
                
                # If the file is not too huge, let's load it fully or in chunks
                # For safety, let's read in chunks or load with pd.read_excel if size < 40MB
                if os.path.getsize(path) < 40 * 1024 * 1024:
                    df = pd.read_excel(path, sheet_name=sheet_name)
                    print(f"  Total rows: {len(df)}")
                    
                    if status_col in df.columns:
                        print("  Value counts for status:")
                        print(df[status_col].value_counts(dropna=False).head(5))
                        
                        ft_inproc = df[df[status_col] == 'FT Inprocessing']
                        print(f"  Total FT Inprocessing in Excel: {len(ft_inproc)}")
                        
                        if ft_cols:
                            ft_col = ft_cols[0]
                            ft_inproc_excl = ft_inproc[ft_inproc[ft_col] != 'vtp_marlo.delacruz']
                            print(f"  Total FT Inprocessing (excl. marlo.delacruz) in Excel: {len(ft_inproc_excl)}")
                else:
                    print("  File is too large for full load, reading in chunks...")
                    # Read in chunks
                    total_rows = 0
                    ft_inproc_count = 0
                    ft_inproc_excl_count = 0
                    
                    for chunk in pd.read_excel(path, sheet_name=sheet_name, chunksize=10000):
                        total_rows += len(chunk)
                        if status_col in chunk.columns:
                            ft_inproc_chunk = chunk[chunk[status_col] == 'FT Inprocessing']
                            ft_inproc_count += len(ft_inproc_chunk)
                            if ft_cols:
                                ft_col = ft_cols[0]
                                ft_inproc_excl_chunk = ft_inproc_chunk[ft_inproc_chunk[ft_col] != 'vtp_marlo.delacruz']
                                ft_inproc_excl_count += len(ft_inproc_excl_chunk)
                    
                    print(f"  Total rows: {total_rows}")
                    print(f"  Total FT Inprocessing in Excel: {ft_inproc_count}")
                    print(f"  Total FT Inprocessing (excl. marlo.delacruz) in Excel: {ft_inproc_excl_count}")
        except Exception as e:
            print(f"  Error reading {filename}: {e}")

if __name__ == '__main__':
    check_parent_excels()
