import sqlite3
import os

def inspect_cortes():
    db_path = 'Reporte FTTH/olt_auditoria.db'
    if not os.path.exists(db_path):
        print("Database not found.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Print columns
    cursor.execute("PRAGMA table_info(cortes)")
    print("Columns in 'cortes' table:")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
        
    # 2. Get first 5 rows
    print("\nSample 5 rows:")
    cursor.execute("SELECT * FROM cortes LIMIT 5")
    rows = cursor.fetchall()
    col_names = [col[1] for col in columns]
    for r in rows:
        row_dict = dict(zip(col_names, r))
        print(row_dict)
        
    # 3. Check values in potential cause/type columns
    # We can check if there are columns like cause, type, etc.
    # Let's count some values dynamically.
    print("\nDistinct values in columns that might indicate energy vs ODN:")
    # We'll check column names from the PRAGMA output
    potential_cols = ['causa', 'tipo_corte', 'tipo', 'causa_corte', 'causa_principal']
    for p_col in potential_cols:
        if p_col in col_names:
            cursor.execute(f"SELECT {p_col}, COUNT(*) FROM cortes GROUP BY {p_col} ORDER BY COUNT(*) DESC LIMIT 10")
            print(f"  Column '{p_col}':")
            for val, cnt in cursor.fetchall():
                print(f"    {val}: {cnt}")
                
    conn.close()

if __name__ == '__main__':
    inspect_cortes()
