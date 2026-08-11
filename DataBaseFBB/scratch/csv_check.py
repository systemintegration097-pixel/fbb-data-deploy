import pandas as pd

def check_csv():
    df = pd.read_csv('scratch/data/INCIDENTS.csv')
    print("CSV loaded successfully.")
    print(f"Total rows in CSV: {len(df)}")
    
    # Check month column name (it has a special character, usually Mes/año or similar)
    month_col = [c for c in df.columns if 'mes' in c.lower() or 'month' in c.lower()][0]
    print(f"Month column name: '{month_col}'")
    
    # 1. Group by month_year and see total vs FT Inprocessing
    print("\nCSV Monthly breakdown (Total vs WO Status = FT Inprocessing):")
    monthly = df.groupby(month_col).agg(
        total_rows=('WO code', 'count'),
        pending_wo_status=('WO Status', lambda x: (x == 'FT Inprocessing').sum()),
        pending_wo_status_excl_marlo=('WO Status', lambda x: ((df.loc[x.index, 'WO Status'] == 'FT Inprocessing') & (df.loc[x.index, 'FT'] != 'vtp_marlo.delacruz')).sum()),
        status_desc_pending=('STATUS', lambda x: (x == 'Pendiente').sum())
    ).reset_index()
    print(monthly)
    
    # Let's check WO Status values for the whole CSV
    print("\nWO Status counts in CSV:")
    print(df['WO Status'].value_counts(dropna=False))
    
    # Let's check if there are WO_code values that don't match standard prefix or anything
    print("\nWO Code prefix analysis:")
    df['prefix'] = df['WO code'].astype(str).str[:3]
    print(df['prefix'].value_counts(dropna=False).head(5))

    # Let's check how many rows are in the Excel if we do WO Status == FT Inprocessing
    total_ft_inproc = (df['WO Status'] == 'FT Inprocessing').sum()
    total_ft_inproc_excl_marlo = ((df['WO Status'] == 'FT Inprocessing') & (df['FT'] != 'vtp_marlo.delacruz')).sum()
    print(f"\nTotal FT Inprocessing in CSV: {total_ft_inproc}")
    print(f"Total FT Inprocessing (excl. marlo.delacruz) in CSV: {total_ft_inproc_excl_marlo}")

if __name__ == '__main__':
    check_csv()
