import sqlite3
import pandas as pd

def compare():
    conn = sqlite3.connect('fbb_database.db')
    db_df = pd.read_sql_query("SELECT * FROM incidents", conn)
    conn.close()
    
    csv_df = pd.read_csv('scratch/data/INCIDENTS.csv')
    
    # Standardize column names/types
    month_col = [c for c in csv_df.columns if 'mes' in c.lower() or 'month' in c.lower()][0]
    
    print("Database total incidents:", len(db_df))
    print("CSV total incidents:", len(csv_df))
    
    # Let's count STATUS=Pendiente in DB vs CSV for each month
    print("\nSTATUS = 'Pendiente' by month:")
    print(f"{'Month':<10} | {'DB Count':<10} | {'CSV Count':<10}")
    print("-" * 35)
    for m in sorted(csv_df[month_col].dropna().unique()):
        db_cnt = len(db_df[(db_df['month_year'] == m) & (db_df['status_desc'] == 'Pendiente')])
        csv_cnt = len(csv_df[(csv_df[month_col] == m) & (csv_df['STATUS'] == 'Pendiente')])
        print(f"{m:<10} | {db_cnt:<10} | {csv_cnt:<10}")
        
    # Let's count WO Status = 'FT Inprocessing' by month
    print("\nWO Status = 'FT Inprocessing' by month:")
    print(f"{'Month':<10} | {'DB Count':<10} | {'CSV Count':<10}")
    print("-" * 35)
    for m in sorted(csv_df[month_col].dropna().unique()):
        db_cnt = len(db_df[(db_df['month_year'] == m) & (db_df['wo_status'] == 'FT Inprocessing')])
        csv_cnt = len(csv_df[(csv_df[month_col] == m) & (csv_df['WO Status'] == 'FT Inprocessing')])
        print(f"{m:<10} | {db_cnt:<10} | {csv_cnt:<10}")

    # Let's see what is going on with the vtp_marlo.delacruz filter
    print("\nWO Status = 'FT Inprocessing' and FT != 'vtp_marlo.delacruz' by month:")
    print(f"{'Month':<10} | {'DB Count':<10} | {'CSV Count':<10}")
    print("-" * 35)
    for m in sorted(csv_df[month_col].dropna().unique()):
        db_cnt = len(db_df[(db_df['month_year'] == m) & (db_df['wo_status'] == 'FT Inprocessing') & (db_df['ft'] != 'vtp_marlo.delacruz')])
        csv_cnt = len(csv_df[(csv_df[month_col] == m) & (csv_df['WO Status'] == 'FT Inprocessing') & (csv_df['FT'] != 'vtp_marlo.delacruz')])
        print(f"{m:<10} | {db_cnt:<10} | {csv_cnt:<10}")

if __name__ == '__main__':
    compare()
