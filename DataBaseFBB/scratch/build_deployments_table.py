import sqlite3
import pandas as pd
import os

def build_deployments_table():
    main_db = "fbb_database.db"
    csv_path = "scratch/List_Deployed.csv"
    
    if not os.path.exists(csv_path):
        print(f"Source file {csv_path} not found. Please run download script first.")
        return
        
    print("Loading deployments CSV...")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"Loaded {len(df)} rows.")
    
    # Map columns dynamically to avoid encoding issues (e.g. 'mes/a\u00f1o')
    col_mapping = {}
    for c in df.columns:
        c_lower = c.lower().strip()
        if 'partner' in c_lower:
            col_mapping[c] = 'partner'
        elif c_lower == 'branch':
            col_mapping[c] = 'branch'
        elif 'kpi' in c_lower and 'paid' in c_lower:
            col_mapping[c] = 'kpi_from_paid'
        elif 'close' in c_lower and 'paid' in c_lower and 'time' in c_lower:
            col_mapping[c] = 'close_time_hrs'
        elif 'station' in c_lower and 'code' in c_lower:
            col_mapping[c] = 'station_code'
        elif 'mes' in c_lower and 'closed' in c_lower:
            col_mapping[c] = 'month_year'
            
    print("Column mapping:", col_mapping)
    
    # Filter columns
    df_filtered = df[list(col_mapping.keys())].copy()
    df_filtered.rename(columns=col_mapping, inplace=True)
    
    # Clean up data
    df_filtered['partner'] = df_filtered['partner'].astype(str).str.strip()
    df_filtered['branch'] = df_filtered['branch'].astype(str).str.strip()
    df_filtered['kpi_from_paid'] = df_filtered['kpi_from_paid'].astype(str).str.strip()
    df_filtered['station_code'] = df_filtered['station_code'].astype(str).str.strip()
    df_filtered['month_year'] = df_filtered['month_year'].astype(str).str.strip()
    
    # Clean close_time_hrs (replace comma with dot and convert to float)
    def clean_hours(val):
        if pd.isna(val):
            return None
        val_str = str(val).strip().replace(',', '.')
        try:
            return float(val_str)
        except ValueError:
            return None
            
    df_filtered['close_time_hrs'] = df_filtered['close_time_hrs'].apply(clean_hours)
    
    # Connect to SQLite
    conn = sqlite3.connect(main_db)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS deployments;")
    cursor.execute("""
        CREATE TABLE deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner TEXT,
            branch TEXT,
            kpi_from_paid TEXT,
            close_time_hrs REAL,
            station_code TEXT,
            month_year TEXT
        );
    """)
    conn.commit()
    
    # Insert in batches
    df_filtered.to_sql("deployments", conn, if_exists="append", index=False)
    
    # Create indexes for fast querying
    cursor.execute("CREATE INDEX idx_deployments_partner ON deployments(partner);")
    cursor.execute("CREATE INDEX idx_deployments_branch ON deployments(branch);")
    cursor.execute("CREATE INDEX idx_deployments_month ON deployments(month_year);")
    conn.commit()
    
    # Validation
    cursor.execute("SELECT COUNT(*) FROM deployments;")
    print("Total rows imported in deployments table:", cursor.fetchone()[0])
    
    cursor.execute("SELECT * FROM deployments LIMIT 5;")
    print("Sample rows:")
    for r in cursor.fetchall():
        print(r)
        
    conn.close()
    print("deployments table built successfully!")

if __name__ == "__main__":
    build_deployments_table()
