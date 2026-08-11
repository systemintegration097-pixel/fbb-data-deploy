import pandas as pd

def check_csv_detailed():
    df = pd.read_csv('scratch/data/INCIDENTS.csv')
    month_col = [c for c in df.columns if 'mes' in c.lower() or 'month' in c.lower()][0]
    
    # Calculate for each month
    print("CSV Monthly Breakdown details:")
    print(f"{'Month':<10} | {'Total Rows':<10} | {'FT Inprocessing (All)':<22} | {'FT Inprocessing (Excl Marlo)':<30} | {'STATUS=Pendiente':<16}")
    print("-" * 100)
    
    for month in sorted(df[month_col].dropna().unique()):
        sub_df = df[df[month_col] == month]
        total = len(sub_df)
        inproc_all = (sub_df['WO Status'] == 'FT Inprocessing').sum()
        inproc_excl = ((sub_df['WO Status'] == 'FT Inprocessing') & (sub_df['FT'] != 'vtp_marlo.delacruz')).sum()
        pendiente_status = (sub_df['STATUS'] == 'Pendiente').sum()
        print(f"{month:<10} | {total:<10} | {inproc_all:<22} | {inproc_excl:<30} | {pendiente_status:<16}")

if __name__ == '__main__':
    check_csv_detailed()
