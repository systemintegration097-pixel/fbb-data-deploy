import sqlite3
import pandas as pd

def analyze():
    conn = sqlite3.connect("fbb_database.db")
    cursor = conn.cursor()
    
    print("=== Table columns in fbb_database ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    for t in tables:
        cursor.execute(f"PRAGMA table_info({t});")
        print(f"Table: {t}, Columns: {[r[1] for r in cursor.fetchall()]}")

    print("\n=== Sample of incidents ===")
    df_inc = pd.read_sql_query("SELECT * FROM incidents LIMIT 5;", conn)
    print(df_inc)

    print("\n=== How many distinct subscribers in incidents? ===")
    cursor.execute("SELECT COUNT(DISTINCT subscriber) FROM incidents;")
    print("Distinct subscribers:", cursor.fetchone()[0])
    
    print("\n=== How many incidents per subscriber (top 5)? ===")
    df_top_sub = pd.read_sql_query("SELECT subscriber, COUNT(*) as count FROM incidents GROUP BY subscriber ORDER BY count DESC LIMIT 5;", conn)
    print(df_top_sub)
    
    print("\n=== Are there any subscribers who cancel? ===")
    # Let's check if the subscriber name has 'cancel' or if there is any indication
    df_cancel_sub = pd.read_sql_query("SELECT subscriber, status_desc, month_year FROM incidents WHERE subscriber LIKE '%cancel%' OR subscriber LIKE '%baja%' LIMIT 5;", conn)
    print(df_cancel_sub)

    # Let's inspect the olt_auditoria.db cuts and outages
    print("\n=== OLT Auditoria Cortes Sample ===")
    try:
        conn_olt = sqlite3.connect("Reporte FTTH/olt_auditoria.db")
        df_cortes = pd.read_sql_query("SELECT * FROM cortes LIMIT 5;", conn_olt)
        print(df_cortes)
        conn_olt.close()
    except Exception as e:
        print("Error reading olt_auditoria:", e)

    conn.close()

if __name__ == "__main__":
    analyze()
