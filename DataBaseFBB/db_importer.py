import urllib.request
import os
import sqlite3
import pandas as pd
import numpy as np
import datetime


SHEET_ID = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
GIDS = {
    "Active_Zones": "0",
    "List_of_Boxes": "1114839336",
    "Staff": "657972808",
    "ZONAS": "106196166",
    "INCIDENTS": "215150019",
    "List_Deployed": "2134446890"
}

DB_PATH = os.path.join(os.path.dirname(__file__), "fbb_database.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "scratch", "data")

def download_csvs():
    os.makedirs(DATA_DIR, exist_ok=True)
    for name, gid in GIDS.items():
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            csv_data = response.read()
        
        file_path = os.path.join(DATA_DIR, f"{name}.csv")
        with open(file_path, "wb") as f:
            f.write(csv_data)
    return True

def clean_numeric(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ['nan', 'null', '-', 'none'] or val_str.startswith('#'):
        return None
    
    is_pct = '%' in val_str
    val_str = val_str.replace('%', '').strip()
    
    if ',' in val_str:
        if '.' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '.')
            
    try:
        res = float(val_str)
        if is_pct:
            res = res / 100.0
        if res.is_integer():
            return int(res)
        return res
    except ValueError:
        return None

def standardize_date(date_str):
    if not date_str or pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    for fmt in ('%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M'):
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    return date_str

def get_week_number(date_str):
    if not date_str or pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    for fmt in ('%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-W%W')
        except ValueError:
            continue
    return None


def import_to_sqlite():
    # 1. Load Active_Zones
    csv_az = os.path.join(DATA_DIR, "Active_Zones.csv")
    if not os.path.exists(csv_az):
        raise FileNotFoundError(f"Missing {csv_az}. Download first.")
        
    df_az = pd.read_csv(csv_az, header=1)
    df_az_data = df_az.iloc[1:].copy() # Drop summary row
    df_az_data = df_az_data.iloc[:, 0:35].copy() # Keep first 35 columns
    
    df_az_data.columns = [
        "n_seq", "branch", "zone", "saturation", "active_customers", "suspended_customers", "canceled_customers",
        "type_infrastructure", "note", "status_service", "site_physical", "site_logical", "previous_site",
        "olt", "port", "ip_mgt", "line", "comments", "boxes_count", "qty_ports_box", "qty_ports_olt_port",
        "department", "province", "district", "ccpp", "postal_code", "status_nims",
        "handover_ready_for_business", "handover_ready_for_business_2", "electrical_company",
        "qty_poles", "comments_extra", "ems", "percent_cancel", "percent_saturation"
    ]
    df_az_data.dropna(subset=['zone'], inplace=True)
    
    # 2. Load List_of_Boxes
    csv_lb = os.path.join(DATA_DIR, "List_of_Boxes.csv")
    if not os.path.exists(csv_lb):
        raise FileNotFoundError(f"Missing {csv_lb}. Download first.")
        
    df_lb = pd.read_csv(csv_lb, skiprows=2)
    df_lb_data = df_lb.iloc[1:].copy() # Drop summary row
    
    df_lb_data.columns = [
        "branch", "zone", "infrastructure", "note", "status_service", "site_physical", "site_logical",
        "olt", "node_code", "box_class", "box_type", "department", "latitude", "longitude",
        "port_used", "update_time"
    ]
    df_lb_data.dropna(subset=['node_code'], inplace=True)
    
    # 3. Load Staff
    csv_sf = os.path.join(DATA_DIR, "Staff.csv")
    if not os.path.exists(csv_sf):
        raise FileNotFoundError(f"Missing {csv_sf}. Download first.")
        
    df_sf = pd.read_csv(csv_sf)
    df_sf_data = df_sf.iloc[:, 0:11].copy() # Keep first 11 columns
    
    df_sf_data.columns = [
        "branch", "staff_team", "warranty_period", "partner", "unnamed_4", "vtp_username", "partner_alt", "br_code", "unnamed_8", "site", "partner_incidence"
    ]
    df_sf_data = df_sf_data[["branch", "staff_team", "warranty_period", "partner", "vtp_username"]].copy()
    df_sf_data.dropna(subset=['staff_team'], inplace=True)
    
    # Strip spaces and deduplicate case-insensitively
    df_sf_data['staff_team'] = df_sf_data['staff_team'].astype(str).str.strip()
    df_sf_data['staff_team_lower'] = df_sf_data['staff_team'].str.lower()
    df_sf_data.drop_duplicates(subset=['staff_team_lower'], keep='first', inplace=True)
    df_sf_data.drop(columns=['staff_team_lower'], inplace=True)
    
    # 4. Load ZONAS (Assignments & Capacities)
    csv_za = os.path.join(DATA_DIR, "ZONAS.csv")
    if not os.path.exists(csv_za):
        raise FileNotFoundError(f"Missing {csv_za}. Download first.")
        
    df_za = pd.read_csv(csv_za)
    
    # Left part: zone assignments (columns 0 to 7)
    df_za_left = df_za.iloc[:, 0:8].copy()
    df_za_left.columns = [
        "zone", "site", "olt", "branch", "partner", "team_distribution", "incidents_distribution", "incidents_distribution_by_team"
    ]
    df_za_left.dropna(subset=['zone'], inplace=True)
    
    # Right part: partner capacities (columns 10 to 16)
    df_za_right = pd.DataFrame()
    if df_za.shape[1] >= 17:
        df_za_right = df_za.iloc[:, 10:17].copy()
        df_za_right.columns = [
            "branch", "partner", "teams_total", "ft_total", "teams_deploy", "teams_incidents", "teams_odn"
        ]
        df_za_right.dropna(subset=['partner'], inplace=True)
        
    # 5. Load INCIDENTS
    csv_inc = os.path.join(DATA_DIR, "INCIDENTS.csv")
    df_inc = pd.DataFrame()
    if os.path.exists(csv_inc):
        try:
            df_inc = pd.read_csv(csv_inc, encoding='utf-8')
        except UnicodeDecodeError:
            df_inc = pd.read_csv(csv_inc, encoding='latin-1')
            
        wo_col_candidates = [c for c in df_inc.columns if 'wo' in c.lower() and 'code' in c.lower()]
        if wo_col_candidates:
            wo_col = wo_col_candidates[0]
            df_inc = df_inc[df_inc[wo_col].astype(str).str.startswith('WO_', na=False)].copy()
            
            def find_col(keywords, default):
                for c in df_inc.columns:
                    if any(kw in c.lower() for kw in keywords):
                        return c
                return default
                
            status_col = 'STATUS'
            status_col_exact = [c for c in df_inc.columns if c.strip() == 'STATUS']
            if status_col_exact:
                status_col = status_col_exact[0]
            else:
                status_cols = [c for c in df_inc.columns if 'status' in c.lower() and 'wo' not in c.lower()]
                if status_cols:
                    status_col = status_cols[0]
                    
            month_col = find_col(['mes', 'month'], 'Mes/ao')
            sub_col = find_col(['subscriber', 'client', 'abo'], 'Subscribers')
            site_col = find_col(['station', 'site'], 'Station code')
            branch_col = find_col(['branch', 'sucursal'], 'BRANCH')
            partner_col = find_col(['partner'], 'Partner Close')
            create_col = find_col(['create', 'fecha'], 'Create Time')
            close_col = find_col(['close', 'cerrar'], 'Closed Time(yyyy-MM-dd)')
            ft_col = 'FT'
            ft_col_exact = [c for c in df_inc.columns if c.strip() == 'FT']
            if ft_col_exact:
                ft_col = ft_col_exact[0]
            res_time_col = find_col(['resolution', 'tiempo'], 'Resolution time')
            kpi_col = find_col(['kpi'], 'KPI Closing')
            repeat_col = find_col(['repeat', 'repeat time', 'qty repeat'], 'Qty repeat time by account (Total record)')
    
    # Clean numeric columns
    numeric_cols_az = ["n_seq", "active_customers", "suspended_customers", "canceled_customers", 
                        "boxes_count", "qty_ports_box", "qty_ports_olt_port", "qty_poles"]
    for col in numeric_cols_az:
        df_az_data[col] = df_az_data[col].apply(clean_numeric)
    df_az_data["saturation"] = df_az_data["saturation"].apply(clean_numeric)
    df_az_data["percent_cancel"] = df_az_data["percent_cancel"].apply(clean_numeric)
    df_az_data["percent_saturation"] = df_az_data["percent_saturation"].apply(clean_numeric)

    numeric_cols_lb = ["latitude", "longitude"]
    for col in numeric_cols_lb:
        df_lb_data[col] = df_lb_data[col].apply(clean_numeric)
        
    df_sf_data["warranty_period"] = df_sf_data["warranty_period"].apply(clean_numeric)

    # Drop duplicate node_codes for unique constraint
    df_lb_data.drop_duplicates(subset=['node_code'], keep='first', inplace=True)

    # Database operations
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Migrate or create tables
    tables = {
        "zones": """
            CREATE TABLE zones (
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
                percent_cancel REAL,
                percent_saturation REAL,
                locally_modified INTEGER DEFAULT 0
            )
        """,
        "boxes": """
            CREATE TABLE boxes (
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
                update_time TEXT,
                locally_modified INTEGER DEFAULT 0
            )
        """,
        "staff": """
            CREATE TABLE staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch TEXT,
                staff_team TEXT UNIQUE,
                warranty_period INTEGER,
                partner TEXT,
                vtp_username TEXT,
                locally_modified INTEGER DEFAULT 0
            )
        """,
        "zone_assignments": """
            CREATE TABLE zone_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone TEXT,
                site TEXT,
                olt TEXT,
                branch TEXT,
                partner TEXT,
                team_distribution TEXT,
                incidents_distribution TEXT,
                incidents_distribution_by_team TEXT,
                locally_modified INTEGER DEFAULT 0
            )
        """,
        "partner_capacities": """
            CREATE TABLE partner_capacities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch TEXT,
                partner TEXT,
                teams_total INTEGER,
                ft_total INTEGER,
                teams_deploy INTEGER,
                teams_incidents INTEGER,
                teams_odn INTEGER,
                locally_modified INTEGER DEFAULT 0,
                UNIQUE(branch, partner)
            )
        """,
        "incidents": """
            CREATE TABLE incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wo_code TEXT UNIQUE,
                wo_status TEXT,
                create_time TEXT,
                ft TEXT,
                closed_time TEXT,
                subscriber TEXT,
                station_code TEXT,
                resolution_time REAL,
                kpi_closing TEXT,
                branch TEXT,
                partner_close TEXT,
                month_year TEXT,
                qty_repeat INTEGER,
                status_desc TEXT,
                week_number TEXT,
                locally_modified INTEGER DEFAULT 0
            )
        """,
        "deployments": """
            CREATE TABLE deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partner TEXT,
                branch TEXT,
                kpi_from_paid TEXT,
                close_time_hrs REAL,
                station_code TEXT,
                month_year TEXT,
                locally_modified INTEGER DEFAULT 0
            )
        """,
        "olt_cortes": """
            CREATE TABLE olt_cortes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_detectado TEXT,
                olt_name TEXT,
                olt_ip TEXT,
                pon TEXT,
                tipo_corte TEXT,
                hora_corte TEXT,
                onus_afectadas INTEGER,
                causa TEXT,
                onus_ids TEXT,
                site TEXT,
                month_year TEXT,
                week_number TEXT
            )
        """
    }
    
    for table_name, create_sql in tables.items():
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        row = cursor.fetchone()
        if not row:
            cursor.execute(create_sql)
        else:
            # Check for columns and alter dynamically
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [c[1] for c in cursor.fetchall()]
            if "locally_modified" not in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN locally_modified INTEGER DEFAULT 0")
            if table_name == "zones":
                if "percent_cancel" not in columns:
                    cursor.execute("ALTER TABLE zones ADD COLUMN percent_cancel REAL")
                if "percent_saturation" not in columns:
                    cursor.execute("ALTER TABLE zones ADD COLUMN percent_saturation REAL")
            if table_name == "incidents":
                if "week_number" not in columns:
                    cursor.execute("ALTER TABLE incidents ADD COLUMN week_number TEXT")
                
    # Re-create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_boxes_zone ON boxes(zone)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_boxes_node_code ON boxes(node_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_zones_zone ON zones(zone)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_team ON staff(staff_team)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_zone ON zone_assignments(zone)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_wo ON incidents(wo_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_site ON incidents(station_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_olt_cortes_site ON olt_cortes(site)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_olt_cortes_month ON olt_cortes(month_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_olt_cortes_week ON olt_cortes(week_number)")
    
    conn.commit()
    
    # 2. Insert or update zones
    zones_imported = 0
    for _, row in df_az_data.iterrows():
        zone_name = str(row["zone"]).strip()
        cursor.execute("SELECT id, locally_modified FROM zones WHERE zone = ?", (zone_name,))
        db_row = cursor.fetchone()
        
        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        
        if not db_row:
            cols = list(row_dict.keys()) + ["locally_modified"]
            vals = list(row_dict.values()) + [0]
            placeholders = ", ".join(["?"] * len(cols))
            cursor.execute(f"INSERT INTO zones ({', '.join(cols)}) VALUES ({placeholders})", vals)
            zones_imported += 1
        else:
            db_id, lm = db_row
            if lm == 0:
                set_clause = ", ".join([f"{k} = ?" for k in row_dict.keys()])
                vals = list(row_dict.values()) + [db_id]
                cursor.execute(f"UPDATE zones SET {set_clause} WHERE id = ?", vals)
                zones_imported += 1
                
    # 3. Insert or update boxes
    boxes_imported = 0
    df_lb_data.drop_duplicates(subset=['node_code'], keep='first', inplace=True)
    for _, row in df_lb_data.iterrows():
        node_code = str(row["node_code"]).strip()
        cursor.execute("SELECT id, locally_modified FROM boxes WHERE node_code = ?", (node_code,))
        db_row = cursor.fetchone()
        
        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        
        if not db_row:
            cols = list(row_dict.keys()) + ["locally_modified"]
            vals = list(row_dict.values()) + [0]
            placeholders = ", ".join(["?"] * len(cols))
            cursor.execute(f"INSERT INTO boxes ({', '.join(cols)}) VALUES ({placeholders})", vals)
            boxes_imported += 1
        else:
            db_id, lm = db_row
            if lm == 0:
                set_clause = ", ".join([f"{k} = ?" for k in row_dict.keys()])
                vals = list(row_dict.values()) + [db_id]
                cursor.execute(f"UPDATE boxes SET {set_clause} WHERE id = ?", vals)
                boxes_imported += 1
                
    # 4. Insert or update staff
    staff_imported = 0
    df_sf_data.drop_duplicates(subset=['staff_team'], keep='first', inplace=True)
    for _, row in df_sf_data.iterrows():
        staff_team = str(row["staff_team"]).strip()
        cursor.execute("SELECT id, locally_modified FROM staff WHERE staff_team = ?", (staff_team,))
        db_row = cursor.fetchone()
        
        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        
        if not db_row:
            cols = list(row_dict.keys()) + ["locally_modified"]
            vals = list(row_dict.values()) + [0]
            placeholders = ", ".join(["?"] * len(cols))
            cursor.execute(f"INSERT INTO staff ({', '.join(cols)}) VALUES ({placeholders})", vals)
            staff_imported += 1
        else:
            db_id, lm = db_row
            if lm == 0:
                set_clause = ", ".join([f"{k} = ?" for k in row_dict.keys()])
                vals = list(row_dict.values()) + [db_id]
                cursor.execute(f"UPDATE staff SET {set_clause} WHERE id = ?", vals)
                staff_imported += 1
                
    # 5. Insert or update zone_assignments
    for _, row in df_za_left.iterrows():
        zone = str(row["zone"]).strip()
        team_dist = str(row["team_distribution"]).strip()
        cursor.execute("SELECT id, locally_modified FROM zone_assignments WHERE zone = ? AND team_distribution = ?", (zone, team_dist))
        db_row = cursor.fetchone()
        
        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        
        if not db_row:
            cols = list(row_dict.keys()) + ["locally_modified"]
            vals = list(row_dict.values()) + [0]
            placeholders = ", ".join(["?"] * len(cols))
            cursor.execute(f"INSERT INTO zone_assignments ({', '.join(cols)}) VALUES ({placeholders})", vals)
        else:
            db_id, lm = db_row
            if lm == 0:
                set_clause = ", ".join([f"{k} = ?" for k in row_dict.keys()])
                vals = list(row_dict.values()) + [db_id]
                cursor.execute(f"UPDATE zone_assignments SET {set_clause} WHERE id = ?", vals)
                
    # 6. Insert or update partner_capacities
    if not df_za_right.empty:
        for _, row in df_za_right.iterrows():
            branch = str(row["branch"]).strip()
            partner = str(row["partner"]).strip()
            if not partner or partner.lower() in ['nan', 'none', '']:
                continue
                
            cursor.execute("SELECT id, locally_modified FROM partner_capacities WHERE branch = ? AND partner = ?", (branch, partner))
            db_row = cursor.fetchone()
            
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            
            # Clean numeric capacities
            for col in ["teams_total", "ft_total", "teams_deploy", "teams_incidents", "teams_odn"]:
                val = row_dict.get(col)
                if val is not None:
                    try:
                        if str(val).strip().lower() in ['no realiza', 'nan', '-', 'none', '']:
                            row_dict[col] = 0
                        else:
                            row_dict[col] = int(float(str(val).replace(',', '.')))
                    except ValueError:
                        row_dict[col] = 0
                        
            if not db_row:
                cols = list(row_dict.keys()) + ["locally_modified"]
                vals = list(row_dict.values()) + [0]
                placeholders = ", ".join(["?"] * len(cols))
                cursor.execute(f"INSERT INTO partner_capacities ({', '.join(cols)}) VALUES ({placeholders})", vals)
            else:
                db_id, lm = db_row
                if lm == 0:
                    set_clause = ", ".join([f"{k} = ?" for k in row_dict.keys()])
                    vals = list(row_dict.values()) + [db_id]
                    cursor.execute(f"UPDATE partner_capacities SET {set_clause} WHERE id = ?", vals)
                    
    # 7. Insert or update incidents
    incidents_imported = 0
    if not df_inc.empty:
        for _, row in df_inc.iterrows():
            wo_code = str(row[wo_col]).strip()
            cursor.execute("SELECT id, locally_modified FROM incidents WHERE wo_code = ?", (wo_code,))
            db_row = cursor.fetchone()
            
            # Parse numeric values
            res_time = row.get(res_time_col)
            if pd.isna(res_time):
                res_time = None
            else:
                try:
                    res_time = float(str(res_time).replace(',', '.'))
                except ValueError:
                    res_time = None
                    
            qty_rep = row.get(repeat_col)
            if pd.isna(qty_rep):
                qty_rep = None
            else:
                try:
                    qty_rep = int(float(str(qty_rep)))
                except ValueError:
                    qty_rep = None
                    
            raw_create_time = None if pd.isna(row.get(create_col)) else str(row.get(create_col)).strip()
            std_create_time = standardize_date(raw_create_time)
            week_num = get_week_number(std_create_time)
            
            row_dict = {
                "wo_code": wo_code,
                "wo_status": None if pd.isna(row.get('WO Status')) else str(row.get('WO Status')).strip(),
                "create_time": std_create_time,
                "ft": None if pd.isna(row.get(ft_col)) else str(row.get(ft_col)).strip(),
                "closed_time": None if pd.isna(row.get(close_col)) else str(row.get(close_col)).strip(),
                "subscriber": None if pd.isna(row.get(sub_col)) else str(row.get(sub_col)).strip(),
                "station_code": None if pd.isna(row.get(site_col)) else str(row.get(site_col)).strip(),
                "resolution_time": res_time,
                "kpi_closing": None if pd.isna(row.get(kpi_col)) else str(row.get(kpi_col)).strip(),
                "branch": None if pd.isna(row.get(branch_col)) else str(row.get(branch_col)).strip(),
                "partner_close": None if pd.isna(row.get(partner_col)) else str(row.get(partner_col)).strip(),
                "month_year": None if pd.isna(row.get(month_col)) else str(row.get(month_col)).strip(),
                "qty_repeat": qty_rep,
                "status_desc": None if pd.isna(row.get(status_col)) else str(row.get(status_col)).strip(),
                "week_number": week_num
            }
            
            # Skip pending incidents under vtp_marlo.delacruz as they are error entries
            if row_dict["wo_status"] == 'FT Inprocessing' and row_dict["ft"] == 'vtp_marlo.delacruz':
                if db_row:
                    cursor.execute("DELETE FROM incidents WHERE id = ?", (db_row[0],))
                continue
            
            if not db_row:
                cols = list(row_dict.keys()) + ["locally_modified"]
                vals = list(row_dict.values()) + [0]
                placeholders = ", ".join(["?"] * len(cols))
                cursor.execute(f"INSERT INTO incidents ({', '.join(cols)}) VALUES ({placeholders})", vals)
                incidents_imported += 1
            else:
                db_id, lm = db_row
                if lm == 0:
                    set_clause = ", ".join([f"{k} = ?" for k in row_dict.keys()])
                    vals = list(row_dict.values()) + [db_id]
                    cursor.execute(f"UPDATE incidents SET {set_clause} WHERE id = ?", vals)
                    incidents_imported += 1

    # 6. Load List Deployed (Deployments)
    csv_dep = os.path.join(DATA_DIR, "List_Deployed.csv")
    deployments_imported = 0
    if os.path.exists(csv_dep):
        try:
            df_dep = pd.read_csv(csv_dep, low_memory=False)
            
            # Map columns dynamically
            col_mapping = {}
            for c in df_dep.columns:
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
            
            if 'partner' in col_mapping.values() and 'branch' in col_mapping.values():
                df_dep_filtered = df_dep[list(col_mapping.keys())].copy()
                df_dep_filtered.rename(columns=col_mapping, inplace=True)
                
                # Delete existing deployments (except locally modified if any)
                cursor.execute("DELETE FROM deployments WHERE locally_modified = 0")
                
                for _, row in df_dep_filtered.iterrows():
                    partner_val = str(row.get('partner')).strip()
                    branch_val = str(row.get('branch')).strip()
                    kpi_val = str(row.get('kpi_from_paid')).strip()
                    station_val = str(row.get('station_code')).strip()
                    my_val = str(row.get('month_year')).strip()
                    
                    raw_hours = row.get('close_time_hrs')
                    hours_val = None
                    if not pd.isna(raw_hours):
                        try:
                            hours_val = float(str(raw_hours).replace(',', '.'))
                        except ValueError:
                            hours_val = None
                            
                    cursor.execute("""
                        INSERT INTO deployments (partner, branch, kpi_from_paid, close_time_hrs, station_code, month_year, locally_modified)
                        VALUES (?, ?, ?, ?, ?, ?, 0)
                    """, (partner_val, branch_val, kpi_val, hours_val, station_val, my_val))
                    deployments_imported += 1
            else:
                # Se saltó TODA la importación en silencio la última vez que la hoja de
                # origen renombró/quitó la columna "Partner" -sin este log, no había forma
                # de notar que "deployments" se quedó desactualizado hasta revisar a mano.
                print(f"ADVERTENCIA: no se encontró columna de 'partner' y/o 'branch' en List_Deployed.csv -- "
                      f"se omite la importación de deployments. Columnas disponibles: {list(df_dep.columns)}")

        except Exception as ex:
            print("Error importing deployments:", ex)

    import_olt_cortes(cursor)
    
    conn.commit()
    conn.close()
    return zones_imported, boxes_imported, staff_imported, incidents_imported, deployments_imported

def import_olt_cortes(cursor):
    print("Starting OLT cuts (outages) import...")
    cursor.execute("DELETE FROM olt_cortes")
    
    db_dir = os.path.join(os.path.dirname(__file__), "Reporte FTTH")
    db_files = []
    if os.path.exists(db_dir):
        for f in os.listdir(db_dir):
            if f.endswith(".db") and f.lower().startswith("olt_auditoria"):
                db_files.append(os.path.join(db_dir, f))
                
    if not db_files:
        print("No OLT auditoria DB files found in Reporte FTTH.")
        return
        
    seen_cuts = set()
    total_imported = 0
    
    for db_path in db_files:
        db_name = os.path.basename(db_path)
        print(f"Reading cuts from OLT DB: {db_name}")
        try:
            conn_olt = sqlite3.connect(db_path)
            conn_olt.row_factory = sqlite3.Row
            cursor_olt = conn_olt.cursor()
            
            cursor_olt.execute("SELECT ts_detectado, olt_name, olt_ip, pon, tipo_corte, hora_corte, onus_afectadas, causa, onus_ids FROM cortes")
            rows = cursor_olt.fetchall()
            
            for r in rows:
                olt_name = str(r['olt_name']).strip() if r['olt_name'] is not None else ""
                pon = str(r['pon']).strip() if r['pon'] is not None else ""
                hora_corte = str(r['hora_corte']).strip() if r['hora_corte'] is not None else ""
                tipo_corte = str(r['tipo_corte']).strip() if r['tipo_corte'] is not None else ""
                
                # Check for uniqueness
                cut_key = (olt_name, pon, hora_corte, tipo_corte)
                if cut_key in seen_cuts:
                    continue
                seen_cuts.add(cut_key)
                
                # Compute extra fields
                site = olt_name[:7] if olt_name else ""
                
                # Parse date standard
                ts_det = standardize_date(r['ts_detectado'])
                h_corte = standardize_date(r['hora_corte'])
                if not h_corte:
                    h_corte = ts_det
                
                month_yr = None
                week_num = None
                
                # Get month_year and week_number
                if h_corte:
                    week_num = get_week_number(h_corte)
                    try:
                        parts = h_corte.split(' ')[0].split('-')
                        if len(parts) == 3:
                            month_yr = f"{parts[1]}/{parts[0]}"
                    except Exception:
                        pass
                
                # Fallback to month_year calculation
                if not month_yr and ts_det:
                    try:
                        parts = ts_det.split(' ')[0].split('-')
                        if len(parts) == 3:
                            month_yr = f"{parts[1]}/{parts[0]}"
                    except Exception:
                        pass
                
                onus_af = 0
                if r['onus_afectadas'] is not None:
                    try:
                        onus_af = int(float(str(r['onus_afectadas'])))
                    except ValueError:
                        pass
                
                cursor.execute("""
                    INSERT INTO olt_cortes (
                        ts_detectado, olt_name, olt_ip, pon, tipo_corte, hora_corte, onus_afectadas, causa, onus_ids, site, month_year, week_number
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ts_det, olt_name, r['olt_ip'], pon, tipo_corte, h_corte, onus_af, r['causa'], r['onus_ids'], site, month_yr, week_num
                ))
                total_imported += 1
                
            conn_olt.close()
            print(f"Finished reading from {db_name}.")
        except Exception as e:
            print(f"Error reading from {db_name}: {e}")
            
    print(f"OLT cuts import finished. Total unique cuts imported: {total_imported}")

def sync_data():
    download_csvs()
    return import_to_sqlite()
