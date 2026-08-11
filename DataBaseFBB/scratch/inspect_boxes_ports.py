import sqlite3
import pandas as pd

def inspect_boxes():
    conn = sqlite3.connect('fbb_database.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM boxes")
    print(f"Total boxes: {cursor.fetchone()[0]}")
    
    # Print sample rows
    print("\nSample 5 boxes:")
    df = pd.read_sql_query("SELECT * FROM boxes LIMIT 5", conn)
    print(df)
    
    # Print distinct value counts of port_used
    print("\nDistinct values in port_used (top 15):")
    df_pu = pd.read_sql_query("SELECT port_used, COUNT(*) as count FROM boxes GROUP BY port_used ORDER BY count DESC LIMIT 15", conn)
    print(df_pu)
    
    # Print distinct value counts of box_type or box_class
    print("\nDistinct values in box_type:")
    df_bt = pd.read_sql_query("SELECT box_type, COUNT(*) as count FROM boxes GROUP BY box_type ORDER BY count DESC", conn)
    print(df_bt)
    
    conn.close()

if __name__ == '__main__':
    inspect_boxes()
