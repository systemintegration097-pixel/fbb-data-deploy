import sqlite3
import pandas as pd
import os

def correlate():
    # 1. Connect to fbb_database.db
    conn = sqlite3.connect("fbb_database.db")
    
    # Let's see incidents count and cancellations count by site
    print("=== Incidents and Cancellations by Site in Main DB ===")
    df_site_inc = pd.read_sql_query("""
        SELECT 
            station_code,
            COUNT(*) as total_wos,
            SUM(CASE WHEN status_desc = 'Cliente cancela' THEN 1 ELSE 0 END) as cancellations,
            ROUND(SUM(CASE WHEN status_desc = 'Cliente cancela' THEN 1.0 ELSE 0.0 END) / COUNT(*), 4) as cancel_ratio
        FROM incidents
        WHERE station_code IS NOT NULL AND station_code != ''
        GROUP BY station_code
        ORDER BY total_wos DESC
        LIMIT 20;
    """, conn)
    print(df_site_inc)

    # Let's inspect the cuts from olt_auditoria.db
    print("\n=== Cuts by OLT in olt_auditoria.db ===")
    if os.path.exists("Reporte FTTH/olt_auditoria.db"):
        conn_olt = sqlite3.connect("Reporte FTTH/olt_auditoria.db")
        # Extract site code from OLT name (e.g. ARE0005OLT01 -> ARE0005)
        df_cuts = pd.read_sql_query("""
            SELECT 
                SUBSTR(olt_name, 1, 7) as site,
                COUNT(*) as total_cuts,
                SUM(onus_afectadas) as total_affected_onus,
                causa
            FROM cortes
            GROUP BY site
            ORDER BY total_cuts DESC
            LIMIT 20;
        """, conn_olt)
        print(df_cuts)
        conn_olt.close()
    else:
        print("olt_auditoria.db not found.")

    conn.close()

if __name__ == "__main__":
    correlate()
