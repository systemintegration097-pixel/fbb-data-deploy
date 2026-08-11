import sqlite3
import pandas as pd

def check_db():
    conn = sqlite3.connect('fbb_database.db')
    print("Database connection opened.")
    
    # 1. Total rows
    total_rows = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    print(f"Total rows in database 'incidents' table: {total_rows}")
    
    # 2. WO Status counts
    print("\nWO Status counts in database:")
    df_wo = pd.read_sql_query("SELECT wo_status, COUNT(*) as count FROM incidents GROUP BY wo_status", conn)
    print(df_wo)
    
    # 3. WO Status counts for FT Inprocessing
    print("\nFT Inprocessing in database:")
    ft_inproc_cnt = conn.execute("SELECT COUNT(*) FROM incidents WHERE wo_status = 'FT Inprocessing'").fetchone()[0]
    print(f"Total FT Inprocessing in database: {ft_inproc_cnt}")
    
    # 4. FT Inprocessing excluding vtp_marlo.delacruz
    ft_inproc_excl = conn.execute("SELECT COUNT(*) FROM incidents WHERE wo_status = 'FT Inprocessing' AND (ft != 'vtp_marlo.delacruz' OR ft IS NULL)").fetchone()[0]
    print(f"Total FT Inprocessing (excl. marlo.delacruz) in database: {ft_inproc_excl}")
    
    # 5. Monthly breakdown
    print("\nMonthly breakdown in database (Total vs FT Inprocessing):")
    df_months = pd.read_sql_query("""
        SELECT 
            month_year, 
            COUNT(*) as total_rows,
            SUM(CASE WHEN wo_status = 'FT Inprocessing' THEN 1 ELSE 0 END) as pending_wo_status,
            SUM(CASE WHEN status_desc = 'Pendiente' THEN 1 ELSE 0 END) as pending_status_desc
        FROM incidents 
        GROUP BY month_year
        ORDER BY month_year ASC
    """, conn)
    print(df_months)
    
    conn.close()

if __name__ == '__main__':
    check_db()
