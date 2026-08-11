import sqlite3
import os

def check_olt_dbs():
    dbs = {
        'olt_auditoria.db': 'Reporte FTTH/olt_auditoria.db',
        'olt_auditoria mAYO.db': 'Reporte FTTH/olt_auditoria mAYO.db'
    }
    
    for name, path in dbs.items():
        if not os.path.exists(path):
            print(f"{name} not found.")
            continue
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        print(f"\nDatabase: {name}")
        
        # Row count
        cursor.execute("SELECT COUNT(*) FROM cortes")
        cnt = cursor.fetchone()[0]
        print(f"  Total rows in 'cortes': {cnt}")
        
        # Min/max dates in hora_corte and ts_detectado
        cursor.execute("SELECT MIN(hora_corte), MAX(hora_corte), MIN(ts_detectado), MAX(ts_detectado) FROM cortes")
        min_h, max_h, min_t, max_t = cursor.fetchone()
        print(f"  hora_corte: {min_h} to {max_h}")
        print(f"  ts_detectado: {min_t} to {max_t}")
        
        # Check value counts for tipo_corte
        cursor.execute("SELECT tipo_corte, COUNT(*) FROM cortes GROUP BY tipo_corte")
        print("  tipo_corte counts:")
        for tc, c in cursor.fetchall():
            print(f"    {tc}: {c}")
            
        conn.close()

if __name__ == '__main__':
    check_olt_dbs()
