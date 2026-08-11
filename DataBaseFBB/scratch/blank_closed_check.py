import pandas as pd

def check_blanks():
    df = pd.read_csv('scratch/data/INCIDENTS.csv')
    print("CSV loaded successfully.")
    
    close_col = [c for c in df.columns if 'close' in c.lower() and 'time' in c.lower()][0]
    print(f"Closed Time column name: '{close_col}'")
    
    # 1. Total empty Closed Time
    empty_closed = df[df[close_col].isna() | (df[close_col].astype(str).str.strip() == '')]
    print(f"Total rows with blank Closed Time: {len(empty_closed)}")
    
    # 2. WO Status for blank Closed Time
    print("\nWO Status counts for rows with blank Closed Time:")
    print(empty_closed['WO Status'].value_counts(dropna=False))
    
    # 3. FT counts for blank Closed Time
    print("\nFT counts for rows with blank Closed Time:")
    print(empty_closed['FT'].value_counts(dropna=False).head(10))
    
    # 4. FT counts for blank Closed Time when WO Status is FT Inprocessing
    inproc_blank = empty_closed[empty_closed['WO Status'] == 'FT Inprocessing']
    print(f"\nFT Inprocessing with blank Closed Time: {len(inproc_blank)}")
    
    # 5. Let's look at FT counts for this subset
    print("FT counts for FT Inprocessing with blank Closed Time:")
    print(inproc_blank['FT'].value_counts(dropna=False).head(10))

    # 6. Let's look at the rows where WO Status is NOT Close
    not_close = df[df['WO Status'] != 'Close']
    print(f"\nTotal rows where WO Status != 'Close': {len(not_close)}")
    print("WO Status counts for WO Status != 'Close':")
    print(not_close['WO Status'].value_counts(dropna=False))
    
    # Exclude vtp_marlo.delacruz from WO Status != 'Close'
    not_close_excl = not_close[not_close['FT'] != 'vtp_marlo.delacruz']
    print(f"Total rows where WO Status != 'Close' and FT != 'vtp_marlo.delacruz': {len(not_close_excl)}")
    print("WO Status for this excluded subset:")
    print(not_close_excl['WO Status'].value_counts(dropna=False))

if __name__ == '__main__':
    check_blanks()
