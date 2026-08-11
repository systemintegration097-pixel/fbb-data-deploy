import os
import sqlite3
import pandas as pd

def search_numbers():
    print("--- 1. Searching in SQLite database ---")
    conn = sqlite3.connect('fbb_database.db')
    
    # Check total pending in DB
    cnt_inproc = conn.execute("SELECT COUNT(*) FROM incidents WHERE wo_status = 'FT Inprocessing'").fetchone()[0]
    cnt_inproc_excl = conn.execute("SELECT COUNT(*) FROM incidents WHERE wo_status = 'FT Inprocessing' AND ft != 'vtp_marlo.delacruz'").fetchone()[0]
    cnt_pendiente = conn.execute("SELECT COUNT(*) FROM incidents WHERE status_desc = 'Pendiente'").fetchone()[0]
    
    print(f"DB total incidents: {conn.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]}")
    print(f"DB WO Status = 'FT Inprocessing': {cnt_inproc}")
    print(f"DB WO Status = 'FT Inprocessing' (excl. marlo): {cnt_inproc_excl}")
    print(f"DB status_desc = 'Pendiente': {cnt_pendiente}")
    
    # Check counts by month for STATUS = 'Pendiente' (including marlo)
    df_db_p = pd.read_sql_query("SELECT month_year, COUNT(*) as cnt FROM incidents WHERE status_desc = 'Pendiente' GROUP BY month_year", conn)
    print("DB 'Pendiente' by month:")
    print(df_db_p)
    
    conn.close()
    
    print("\n--- 2. Searching in INCIDENTS.csv ---")
    df_csv = pd.read_csv('scratch/data/INCIDENTS.csv')
    print(f"CSV total rows: {len(df_csv)}")
    
    # Check different filter combinations
    inproc = df_csv[df_csv['WO Status'] == 'FT Inprocessing']
    inproc_excl = inproc[inproc['FT'] != 'vtp_marlo.delacruz']
    pendiente = df_csv[df_csv['STATUS'] == 'Pendiente']
    pendiente_excl = pendiente[pendiente['FT'] != 'vtp_marlo.delacruz']
    
    print(f"CSV WO Status = 'FT Inprocessing': {len(inproc)}")
    print(f"CSV WO Status = 'FT Inprocessing' (excl. marlo): {len(inproc_excl)}")
    print(f"CSV STATUS = 'Pendiente': {len(pendiente)}")
    print(f"CSV STATUS = 'Pendiente' (excl. marlo): {len(pendiente_excl)}")
    
    # Check where STATUS is NaN
    status_nan = df_csv[df_csv['STATUS'].isna()]
    print(f"CSV STATUS is NaN: {len(status_nan)}")
    print("WO Status for STATUS is NaN:")
    print(status_nan['WO Status'].value_counts(dropna=False))
    
    # What if they filter Closed Time is empty?
    close_col = [c for c in df_csv.columns if 'close' in c.lower() and 'time' in c.lower()][0]
    empty_closed = df_csv[df_csv[close_col].isna() | (df_csv[close_col].astype(str).str.strip() == '')]
    empty_closed_excl = empty_closed[empty_closed['FT'] != 'vtp_marlo.delacruz']
    print(f"CSV Closed Time is empty: {len(empty_closed)}")
    print(f"CSV Closed Time is empty (excl. marlo): {len(empty_closed_excl)}")

if __name__ == '__main__':
    search_numbers()
