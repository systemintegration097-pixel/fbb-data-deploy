import sqlite3
import pandas as pd

def check_incidents_values():
    conn = sqlite3.connect("fbb_database.db")
    
    print("=== Distinct wo_status ===")
    df_wo_status = pd.read_sql_query("SELECT wo_status, COUNT(*) as count FROM incidents GROUP BY wo_status;", conn)
    print(df_wo_status)
    
    print("\n=== Distinct status_desc (top 20) ===")
    df_status_desc = pd.read_sql_query("SELECT status_desc, COUNT(*) as count FROM incidents GROUP BY status_desc ORDER BY count DESC LIMIT 20;", conn)
    print(df_status_desc)

    print("\n=== Sample of incidents with status_desc containing 'baja' or 'cancel' ===")
    df_baja = pd.read_sql_query("SELECT status_desc, COUNT(*) as count FROM incidents WHERE status_desc LIKE '%baja%' OR status_desc LIKE '%cancel%' GROUP BY status_desc;", conn)
    print(df_baja)

    conn.close()

if __name__ == "__main__":
    check_incidents_values()
