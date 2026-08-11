import sqlite3
import pandas as pd
import os

def check_date_ranges_fast():
    print("=== OLT Auditoria DBs Info (FAST) ===")
    dbs = {
        "olt_auditoria.db": "Reporte FTTH/olt_auditoria.db",
        "olt_auditoria mAYO.db": "Reporte FTTH/olt_auditoria mAYO.db"
    }
    
    for name, path in dbs.items():
        if os.path.exists(path):
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Range of ts_detectado in cortes
            cursor.execute("SELECT ts_detectado FROM cortes ORDER BY rowid ASC LIMIT 1;")
            min_ts = cursor.fetchone()
            min_ts = min_ts[0] if min_ts else None
            
            cursor.execute("SELECT ts_detectado FROM cortes ORDER BY rowid DESC LIMIT 1;")
            max_ts = cursor.fetchone()
            max_ts = max_ts[0] if max_ts else None
            
            cursor.execute("SELECT COUNT(*) FROM cortes;")
            cnt = cursor.fetchone()[0]
            print(f"{name} (cortes table):")
            print(f"  Rows: {cnt}")
            print(f"  Range: {min_ts} to {max_ts}")
            
            # Range of ts_scan in escaneos
            cursor.execute("SELECT ts_scan FROM escaneos ORDER BY rowid ASC LIMIT 1;")
            min_scan = cursor.fetchone()
            min_scan = min_scan[0] if min_scan else None
            
            cursor.execute("SELECT ts_scan FROM escaneos ORDER BY rowid DESC LIMIT 1;")
            max_scan = cursor.fetchone()
            max_scan = max_scan[0] if max_scan else None
            
            cursor.execute("SELECT COUNT(*) FROM escaneos;")
            cnt_scan = cursor.fetchone()[0]
            print(f"{name} (escaneos table):")
            print(f"  Rows: {cnt_scan}")
            print(f"  Range: {min_scan} to {max_scan}")
            
            conn.close()
        else:
            print(f"{name} not found.")

    # 2. incidents month range
    conn_main = sqlite3.connect("fbb_database.db")
    cursor_main = conn_main.cursor()
    cursor_main.execute("SELECT month_year, COUNT(*) FROM incidents GROUP BY month_year ORDER BY month_year;")
    print("\n=== Main DB incidents table ===")
    print("  Months in incidents:", cursor_main.fetchall())
    conn_main.close()

if __name__ == "__main__":
    check_date_ranges_fast()
