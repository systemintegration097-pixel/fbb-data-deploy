import sqlite3
import os

def inspect():
    db_paths = [
        'Reporte FTTH/olt_auditoria.db',
        'Reporte FTTH/olt_auditoria mAYO.db'
    ]
    for path in db_paths:
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue
        print(f"\nInspecting database: {path} ({os.path.getsize(path)/1024/1024:.2f} MB)")
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            print("  Tables:", tables)
            for t in tables[:5]:
                cursor.execute(f"SELECT COUNT(*) FROM {t}")
                cnt = cursor.fetchone()[0]
                print(f"    Table '{t}': {cnt} rows")
            conn.close()
        except Exception as e:
            print("  Error:", e)

if __name__ == '__main__':
    inspect()
