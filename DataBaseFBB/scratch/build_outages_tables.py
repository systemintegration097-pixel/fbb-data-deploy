import sqlite3
import pandas as pd
import os

def build_tables():
    main_db = "fbb_database.db"
    conn_main = sqlite3.connect(main_db)
    cursor_main = conn_main.cursor()
    
    # Drop existing tables if any
    cursor_main.execute("DROP TABLE IF EXISTS site_outages;")
    cursor_main.execute("DROP TABLE IF EXISTS site_outage_causes;")
    
    # Recreate tables
    cursor_main.execute("""
        CREATE TABLE site_outages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site TEXT,
            month_year TEXT,
            cuts_count INTEGER,
            affected_onus INTEGER
        );
    """)
    
    cursor_main.execute("""
        CREATE TABLE site_outage_causes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site TEXT,
            month_year TEXT,
            causa TEXT,
            cuts_count INTEGER,
            affected_onus INTEGER
        );
    """)
    
    conn_main.commit()
    
    # Scan for OLT DBs in the Reporte FTTH directory
    db_dir = "Reporte FTTH"
    db_files = []
    if os.path.exists(db_dir):
        for f in os.listdir(db_dir):
            if f.endswith(".db") and f.lower().startswith("olt_auditoria"):
                db_files.append(os.path.join(db_dir, f))
                
    cuts_list = []
    causes_list = []
    
    # Helper function to read from a DB
    def read_db(db_path, db_name):
        if not os.path.exists(db_path):
            print(f"{db_name} not found at {db_path}.")
            return
        
        print(f"Reading from {db_name} ({db_path})...")
        conn_olt = sqlite3.connect(db_path)
        
        # Read cuts for site_outages
        df_cuts = pd.read_sql_query("""
            SELECT 
                SUBSTR(olt_name, 1, 7) as site,
                SUBSTR(ts_detectado, 6, 2) || '/' || SUBSTR(ts_detectado, 1, 4) as month_year,
                COUNT(*) as cuts_count,
                SUM(onus_afectadas) as affected_onus
            FROM cortes
            WHERE olt_name IS NOT NULL AND ts_detectado IS NOT NULL
            GROUP BY site, month_year
        """, conn_olt)
        cuts_list.append(df_cuts)
        
        # Read causes for site_outage_causes
        df_causes = pd.read_sql_query("""
            SELECT 
                SUBSTR(olt_name, 1, 7) as site,
                SUBSTR(ts_detectado, 6, 2) || '/' || SUBSTR(ts_detectado, 1, 4) as month_year,
                COALESCE(causa, 'Otro') as causa,
                COUNT(*) as cuts_count,
                SUM(onus_afectadas) as affected_onus
            FROM cortes
            WHERE olt_name IS NOT NULL AND ts_detectado IS NOT NULL
            GROUP BY site, month_year, causa
        """, conn_olt)
        causes_list.append(df_causes)
        
        conn_olt.close()
        print(f"Finished reading from {db_name}.")
        
    for db_path in db_files:
        db_name = os.path.basename(db_path)
        read_db(db_path, db_name)
    
    if not cuts_list:
        print("No source database found. Exiting.")
        conn_main.close()
        return
        
    # Combine and group cuts
    df_all_cuts = pd.concat(cuts_list, ignore_index=True)
    df_all_cuts = df_all_cuts.groupby(['site', 'month_year']).sum().reset_index()
    
    # Combine and group causes
    df_all_causes = pd.concat(causes_list, ignore_index=True)
    df_all_causes = df_all_causes.groupby(['site', 'month_year', 'causa']).sum().reset_index()
    
    # Save to main DB
    df_all_cuts.to_sql("site_outages", conn_main, if_exists="append", index=False)
    df_all_causes.to_sql("site_outage_causes", conn_main, if_exists="append", index=False)
    
    print("\n=== Validation ===")
    cursor_main.execute("SELECT COUNT(*) FROM site_outages;")
    print(f"Total rows in site_outages: {cursor_main.fetchone()[0]}")
    
    cursor_main.execute("SELECT COUNT(*) FROM site_outage_causes;")
    print(f"Total rows in site_outage_causes: {cursor_main.fetchone()[0]}")
    
    conn_main.commit()
    conn_main.close()
    print("Tables built successfully in fbb_database.db!")

if __name__ == "__main__":
    build_tables()
