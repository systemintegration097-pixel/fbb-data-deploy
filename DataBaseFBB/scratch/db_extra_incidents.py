import sqlite3
import pandas as pd

def check_extra():
    conn = sqlite3.connect('fbb_database.db')
    db_df = pd.read_sql_query("SELECT * FROM incidents", conn)
    conn.close()
    
    csv_df = pd.read_csv('scratch/data/INCIDENTS.csv')
    
    # Check which wo_codes in DB are NOT in CSV
    db_wo_codes = set(db_df['wo_code'].dropna().unique())
    csv_wo_codes = set(csv_df['WO code'].dropna().unique())
    
    extra_wo = db_wo_codes - csv_wo_codes
    print(f"Total wo_codes in DB: {len(db_wo_codes)}")
    print(f"Total wo_codes in CSV: {len(csv_wo_codes)}")
    print(f"Total wo_codes in DB that are NOT in CSV: {len(extra_wo)}")
    
    if extra_wo:
        extra_df = db_df[db_df['wo_code'].isin(extra_wo)]
        print("\nExtra incidents in DB by month:")
        print(extra_df['month_year'].value_counts(dropna=False))
        
        print("\nExtra incidents in DB by WO Status:")
        print(extra_df['wo_status'].value_counts(dropna=False))
        
        print("\nExtra incidents in DB by status_desc:")
        print(extra_df['status_desc'].value_counts(dropna=False))

if __name__ == '__main__':
    check_extra()
