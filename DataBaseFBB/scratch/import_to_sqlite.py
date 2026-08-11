import sqlite3
import pandas as pd
import numpy as np
import os

db_path = "fbb_database.db"

# 1. Load Active_Zones
print("Loading Active_Zones...")
df_az = pd.read_csv("scratch/data/Active_Zones.csv", header=1)
print("Active_Zones raw shape:", df_az.shape)

# Drop the first row (summary row)
df_az_data = df_az.iloc[1:].copy()

# Rename columns by positional list
df_az_data.columns = [
    "n_seq", "branch", "zone", "saturation", "active_customers", "suspended_customers", "canceled_customers",
    "type_infrastructure", "note", "status_service", "site_physical", "site_logical", "previous_site",
    "olt", "port", "ip_mgt", "line", "comments", "boxes_count", "qty_ports_box", "qty_ports_olt_port",
    "department", "province", "district", "ccpp", "postal_code", "status_nims",
    "handover_ready_for_business", "handover_ready_for_business_2", "electrical_company",
    "qty_poles", "comments_extra", "ems", "canceled_customers_2"
]

# Drop rows where zone is empty/NaN
df_az_data.dropna(subset=['zone'], inplace=True)
print("Active_Zones shape after dropping empty zones:", df_az_data.shape)

# 2. Load List_of_Boxes
print("Loading List_of_Boxes...")
df_lb = pd.read_csv("scratch/data/List_of_Boxes.csv", skiprows=2)
print("List_of_Boxes raw shape:", df_lb.shape)

# Drop the first row (summary row)
df_lb_data = df_lb.iloc[1:].copy()

df_lb_data.columns = [
    "branch", "zone", "infrastructure", "note", "status_service", "site_physical", "site_logical",
    "olt", "node_code", "box_class", "box_type", "department", "latitude", "longitude",
    "port_used", "update_time"
]

# Drop rows where node_code is empty/NaN
df_lb_data.dropna(subset=['node_code'], inplace=True)
print("List_of_Boxes shape after dropping empty node codes:", df_lb_data.shape)

# Helper function to clean numeric types
def clean_numeric(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip().replace(',', '')
    if not val_str or val_str.lower() in ['nan', 'null', '-', 'none']:
        return None
    # If it has a %, convert to fraction (e.g. "15.23%" -> 0.1523)
    if '%' in val_str:
        try:
            return float(val_str.replace('%', '')) / 100.0
        except ValueError:
            pass
    try:
        if '.' in val_str:
            return float(val_str)
        else:
            return int(val_str)
    except ValueError:
        return val_str

# Apply numeric cleaning to relevant columns
numeric_cols_az = ["n_seq", "active_customers", "suspended_customers", "canceled_customers", 
                    "boxes_count", "qty_ports_box", "qty_ports_olt_port", "qty_poles", "canceled_customers_2"]
for col in numeric_cols_az:
    df_az_data[col] = df_az_data[col].apply(clean_numeric)

# Saturation is percentage, let's extract it as a float
df_az_data["saturation"] = df_az_data["saturation"].apply(clean_numeric)

numeric_cols_lb = ["latitude", "longitude"]
for col in numeric_cols_lb:
    df_lb_data[col] = df_lb_data[col].apply(clean_numeric)

# Create sqlite connection
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables (removed UNIQUE constraint from zone in zones table)
cursor.execute("""
CREATE TABLE IF NOT EXISTS zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    n_seq INTEGER,
    branch TEXT,
    zone TEXT,
    saturation REAL,
    active_customers INTEGER,
    suspended_customers INTEGER,
    canceled_customers INTEGER,
    type_infrastructure TEXT,
    note TEXT,
    status_service TEXT,
    site_physical TEXT,
    site_logical TEXT,
    previous_site TEXT,
    olt TEXT,
    port TEXT,
    ip_mgt TEXT,
    line TEXT,
    comments TEXT,
    boxes_count INTEGER,
    qty_ports_box INTEGER,
    qty_ports_olt_port INTEGER,
    department TEXT,
    province TEXT,
    district TEXT,
    ccpp TEXT,
    postal_code TEXT,
    status_nims TEXT,
    handover_ready_for_business TEXT,
    handover_ready_for_business_2 TEXT,
    electrical_company TEXT,
    qty_poles INTEGER,
    comments_extra TEXT,
    ems TEXT,
    canceled_customers_2 INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS boxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch TEXT,
    zone TEXT,
    infrastructure TEXT,
    note TEXT,
    status_service TEXT,
    site_physical TEXT,
    site_logical TEXT,
    olt TEXT,
    node_code TEXT UNIQUE,
    box_class TEXT,
    box_type TEXT,
    department TEXT,
    latitude REAL,
    longitude REAL,
    port_used TEXT,
    update_time TEXT
)
""")

# Create indexes for fast queries
cursor.execute("CREATE INDEX IF NOT EXISTS idx_boxes_zone ON boxes(zone)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_boxes_node_code ON boxes(node_code)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_zones_zone ON zones(zone)")

conn.commit()

# Save dataframes to SQL
df_az_data.to_sql("zones", conn, if_exists="append", index=False)
print("Inserted zones:", df_az_data.shape[0])

# Check for duplicate node_codes in List of Boxes that might violate UNIQUE constraint
duplicates = df_lb_data[df_lb_data.duplicated(subset=['node_code'], keep=False)]
if not duplicates.empty:
    print(f"Warning: Found {duplicates.shape[0]} duplicate node_codes in List of Boxes. Dropping duplicates, keeping first.")
    df_lb_data.drop_duplicates(subset=['node_code'], keep='first', inplace=True)

df_lb_data.to_sql("boxes", conn, if_exists="append", index=False)
print("Inserted boxes:", df_lb_data.shape[0])

# Verify count
cursor.execute("SELECT count(*) FROM zones")
print("Zones in DB:", cursor.fetchone()[0])

cursor.execute("SELECT count(*) FROM boxes")
print("Boxes in DB:", cursor.fetchone()[0])

conn.close()
print("Database import complete!")
