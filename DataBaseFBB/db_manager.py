import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "fbb_database.db")

class DBManager:
    @staticmethod
    def get_connection():
        import math
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Register Haversine distance function in SQLite
        def distance(lat1, lon1, lat2, lon2):
            if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
                return 999999999.0
            try:
                lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                return c * 6371000.0 # Distance in meters
            except Exception:
                return 999999999.0
                
        conn.create_function("distance", 4, distance)
        return conn

    @classmethod
    def get_dashboard_stats(cls, branch="", zone=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # Build dynamic where clause for zones queries
        query_parts = ["WHERE 1=1"]
        params = []
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
        if zone:
            query_parts.append("zone = ?")
            params.append(zone)
        where_clause = " AND ".join(query_parts)
        
        # Build dynamic where clause for boxes queries
        box_parts = ["WHERE 1=1"]
        box_params = []
        if branch:
            box_parts.append("branch = ?")
            box_params.append(branch)
        if zone:
            box_parts.append("zone = ?")
            box_params.append(zone)
        box_where_clause = " AND ".join(box_parts)
        
        # 1. General counts
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_zones,
                SUM(active_customers) as total_active_customers,
                SUM(suspended_customers) as total_suspended_customers,
                SUM(canceled_customers) as total_canceled_customers,
                SUM(qty_ports_box) as total_ports
            FROM zones
            {where_clause}
        """, params)
        zones_summary = dict(cursor.fetchone())
        
        cursor.execute(f"SELECT COUNT(*) as total_boxes FROM boxes {box_where_clause}", box_params)
        boxes_summary = dict(cursor.fetchone())
        
        stats = {
            "total_zones": zones_summary["total_zones"],
            "total_boxes": boxes_summary["total_boxes"],
            "total_active": zones_summary["total_active_customers"] or 0,
            "total_suspended": zones_summary["total_suspended_customers"] or 0,
            "total_canceled": zones_summary["total_canceled_customers"] or 0,
            "total_ports": zones_summary["total_ports"] or 0,
        }
        
        # 2. Avg Saturation
        cursor.execute(f"""
            SELECT 
                SUM(COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / 
                SUM(COALESCE(qty_ports_box, 0)) as avg_saturation
            FROM zones 
            {where_clause} AND qty_ports_box IS NOT NULL AND qty_ports_box > 0
        """, params)
        row = cursor.fetchone()
        stats["avg_saturation"] = round((row["avg_saturation"] or 0) * 100, 2)
        
        # 3. Saturation Ranges (<30%, 30-70%, 70-85%, >85%)
        cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN (COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / COALESCE(qty_ports_box, 1) < 0.30 THEN 1 ELSE 0 END) as low,
                SUM(CASE WHEN (COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / COALESCE(qty_ports_box, 1) >= 0.30 AND (COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / COALESCE(qty_ports_box, 1) < 0.70 THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN (COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / COALESCE(qty_ports_box, 1) >= 0.70 AND (COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / COALESCE(qty_ports_box, 1) < 0.85 THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN (COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / COALESCE(qty_ports_box, 1) >= 0.85 THEN 1 ELSE 0 END) as critical
            FROM zones
            {where_clause} AND qty_ports_box IS NOT NULL AND qty_ports_box > 0
        """, params)
        sat_ranges = dict(cursor.fetchone())
        stats["saturation_ranges"] = {
            "low": sat_ranges["low"] or 0,
            "medium": sat_ranges["medium"] or 0,
            "high": sat_ranges["high"] or 0,
            "critical": sat_ranges["critical"] or 0
        }
        
        # 4. Critical Saturated Zones (Top 10)
        cursor.execute(f"""
            SELECT id, zone, branch, 
                   (COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 1.0 / COALESCE(qty_ports_box, 1) as saturation, 
                   active_customers, status_service
            FROM zones
            {where_clause} AND qty_ports_box IS NOT NULL AND qty_ports_box > 0
            ORDER BY saturation DESC
            LIMIT 10
        """, params)
        stats["critical_zones"] = [dict(r) for r in cursor.fetchall()]
        for z in stats["critical_zones"]:
            z["saturation"] = round(z["saturation"] * 100, 2)
            
        # 5. Customers and Boxes by Branch
        cursor.execute(f"""
            SELECT 
                branch, 
                COUNT(zone) as zone_count,
                SUM(COALESCE(active_customers, 0)) as active_sum,
                SUM(COALESCE(suspended_customers, 0)) as suspended_sum,
                SUM(COALESCE(canceled_customers, 0)) as canceled_sum,
                SUM(COALESCE(qty_ports_box, 0)) as total_ports,
                SUM(COALESCE(boxes_count, 0)) as boxes_sum,
                ROUND(
                    CASE WHEN SUM(COALESCE(qty_ports_box, 0)) > 0 THEN 
                        (SUM(COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) * 100.0) / SUM(COALESCE(qty_ports_box, 0))
                    ELSE 0.0 END, 2
                ) as avg_saturation,
                ROUND(
                    CASE WHEN SUM(COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0)) > 0 THEN 
                        (SUM(COALESCE(canceled_customers, 0)) * 100.0) / SUM(COALESCE(active_customers, 0) + COALESCE(suspended_customers, 0) + COALESCE(canceled_customers, 0))
                    ELSE 0.0 END, 2
                ) as percent_cancel
            FROM zones
            {where_clause} AND branch IS NOT NULL AND branch != ''
            GROUP BY branch
            ORDER BY active_sum DESC
        """, params)
        stats["branch_distribution"] = [dict(r) for r in cursor.fetchall()]
        
        # 6. Service Status Breakdown for Boxes
        cursor.execute(f"""
            SELECT status_service, COUNT(*) as count
            FROM boxes
            {box_where_clause} AND status_service IS NOT NULL AND status_service != ''
            GROUP BY status_service
        """, box_params)
        stats["box_status_distribution"] = [dict(r) for r in cursor.fetchall()]
        
        conn.close()
        return stats

    @classmethod
    def get_filter_options(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT branch FROM zones WHERE branch IS NOT NULL AND branch != '' ORDER BY branch")
        branches = [r["branch"] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT department FROM zones WHERE department IS NOT NULL AND department != '' ORDER BY department")
        departments = [r["department"] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT box_class FROM boxes WHERE box_class IS NOT NULL AND box_class != '' ORDER BY box_class")
        box_classes = [r["box_class"] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT partner FROM zone_assignments WHERE partner IS NOT NULL AND partner != '' ORDER BY partner")
        partners = [r["partner"] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT zone FROM zones WHERE zone IS NOT NULL AND zone != '' ORDER BY zone")
        zones = [r["zone"] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT site_logical FROM boxes WHERE site_logical IS NOT NULL AND site_logical != '' ORDER BY site_logical")
        sites = [r["site_logical"] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT zone, branch, partner FROM zone_assignments WHERE zone IS NOT NULL AND branch IS NOT NULL AND partner IS NOT NULL AND partner != '' ORDER BY zone")
        zone_assignments = [dict(r) for r in cursor.fetchall()]
        
        conn.close()
        return {
            "branches": branches,
            "departments": departments,
            "box_classes": box_classes,
            "partners": partners,
            "zones": zones,
            "sites": sites,
            "zone_assignments": zone_assignments
        }

    @classmethod
    def get_zones(cls, page=1, per_page=15, search="", branch="", department="", sort_by="zone", sort_dir="ASC"):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE 1=1"]
        params = []
        
        if search:
            query_parts.append("(zone LIKE ? OR site_physical LIKE ? OR olt LIKE ? OR district LIKE ?)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
            
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
            
        if department:
            query_parts.append("department = ?")
            params.append(department)
            
        where_clause = " AND ".join(query_parts)
        
        cursor.execute(f"SELECT COUNT(*) FROM zones {where_clause}", params)
        total_count = cursor.fetchone()[0]
        
        allowed_sort_cols = ["zone", "branch", "saturation", "active_customers", "status_service", "site_physical", "olt", "department", "percent_saturation", "percent_cancel"]
        if sort_by not in allowed_sort_cols:
            sort_by = "zone"
        if sort_dir.upper() not in ["ASC", "DESC"]:
            sort_dir = "ASC"
            
        offset = (page - 1) * per_page
        query = f"""
            SELECT * FROM zones 
            {where_clause} 
            ORDER BY {sort_by} {sort_dir} 
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [per_page, offset])
        rows = cursor.fetchall()
        
        zones_list = []
        for r in rows:
            z = dict(r)
            if z["saturation"] is not None:
                z["saturation_percent"] = round(z["saturation"] * 100, 2)
            else:
                z["saturation_percent"] = None
                
            if z.get("percent_cancel") is not None:
                z["percent_cancel_formatted"] = round(z["percent_cancel"] * 100, 2)
            else:
                z["percent_cancel_formatted"] = 0.0
                
            if z.get("percent_saturation") is not None:
                z["percent_saturation_formatted"] = round(z["percent_saturation"] * 100, 2)
            else:
                z["percent_saturation_formatted"] = 0.0
                
            zones_list.append(z)
            
        conn.close()
        return {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "pages": (total_count + per_page - 1) // per_page,
            "data": zones_list
        }

    @classmethod
    def get_zone(cls, zone_id):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM zones WHERE id = ?", (zone_id,))
        row = cursor.fetchone()
        
        zone_data = dict(row) if row else None
        if zone_data:
            if zone_data["saturation"] is not None:
                zone_data["saturation_percent"] = round(zone_data["saturation"] * 100, 2)
            else:
                zone_data["saturation_percent"] = None
                
            if zone_data.get("percent_cancel") is not None:
                zone_data["percent_cancel_formatted"] = round(zone_data["percent_cancel"] * 100, 2)
            else:
                zone_data["percent_cancel_formatted"] = 0.0
                
            if zone_data.get("percent_saturation") is not None:
                zone_data["percent_saturation_formatted"] = round(zone_data["percent_saturation"] * 100, 2)
            else:
                zone_data["percent_saturation_formatted"] = 0.0
            
            # Fetch assigned staff details for this zone by joining zone_assignments and staff
            cursor.execute("""
                SELECT 
                    za.team_distribution as staff_team,
                    za.partner,
                    za.olt,
                    za.incidents_distribution_by_team as partner_incidence,
                    s.vtp_username,
                    s.warranty_period
                FROM zone_assignments za
                LEFT JOIN staff s ON LOWER(TRIM(s.staff_team)) = LOWER(TRIM(za.team_distribution))
                WHERE za.zone = ?
                LIMIT 1
            """, (zone_data["zone"],))
            staff_row = cursor.fetchone()
            if staff_row:
                zone_data["staff"] = dict(staff_row)
            else:
                zone_data["staff"] = None
                
        conn.close()
        return zone_data

    @classmethod
    def add_zone(cls, data):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        saturation = data.get("saturation")
        if saturation is not None:
            try:
                saturation = float(saturation)
                if saturation > 1.0:
                    saturation = saturation / 100.0
            except ValueError:
                saturation = None
                
        columns = [
            "n_seq", "branch", "zone", "saturation", "active_customers", "suspended_customers", "canceled_customers",
            "type_infrastructure", "note", "status_service", "site_physical", "site_logical", "previous_site",
            "olt", "port", "ip_mgt", "line", "comments", "boxes_count", "qty_ports_box", "qty_ports_olt_port",
            "department", "province", "district", "ccpp", "postal_code", "status_nims",
            "handover_ready_for_business", "handover_ready_for_business_2", "electrical_company",
            "qty_poles", "comments_extra", "ems", "canceled_customers_2"
        ]
        
        insert_cols = []
        insert_vals = []
        placeholders = []
        
        for col in columns:
            if col in data:
                insert_cols.append(col)
                if col == "saturation":
                    insert_vals.append(saturation)
                else:
                    insert_vals.append(data[col])
                placeholders.append("?")
                
        # Mark as locally modified
        insert_cols.append("locally_modified")
        insert_vals.append(1)
        placeholders.append("?")
                
        query = f"INSERT INTO zones ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(query, insert_vals)
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id

    @classmethod
    def update_zone(cls, zone_id, data):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        saturation = data.get("saturation")
        if saturation is not None:
            try:
                saturation = float(saturation)
                if saturation > 1.0:
                    saturation = saturation / 100.0
            except ValueError:
                saturation = None
                
        columns = [
            "n_seq", "branch", "zone", "saturation", "active_customers", "suspended_customers", "canceled_customers",
            "type_infrastructure", "note", "status_service", "site_physical", "site_logical", "previous_site",
            "olt", "port", "ip_mgt", "line", "comments", "boxes_count", "qty_ports_box", "qty_ports_olt_port",
            "department", "province", "district", "ccpp", "postal_code", "status_nims",
            "handover_ready_for_business", "handover_ready_for_business_2", "electrical_company",
            "qty_poles", "comments_extra", "ems", "canceled_customers_2"
        ]
        
        update_pairs = []
        update_vals = []
        
        for col in columns:
            if col in data:
                update_pairs.append(f"{col} = ?")
                if col == "saturation":
                    update_vals.append(saturation)
                else:
                    update_vals.append(data[col])
                    
        if not update_pairs:
            conn.close()
            return False
            
        # Mark as locally modified
        update_pairs.append("locally_modified = 1")
        query = f"UPDATE zones SET {', '.join(update_pairs)} WHERE id = ?"
        update_vals.append(zone_id)
        
        cursor.execute(query, update_vals)
        conn.commit()
        changes = conn.total_changes > 0
        conn.close()
        return changes

    @classmethod
    def delete_zone(cls, zone_id):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
        conn.commit()
        changes = conn.total_changes > 0
        conn.close()
        return changes

    @classmethod
    def get_boxes(cls, page=1, per_page=15, search="", zone="", olt="", branch="", box_class="", site_logical="", sort_by="node_code", sort_dir="ASC"):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE 1=1"]
        params = []
        
        if search:
            query_parts.append("(node_code LIKE ? OR note LIKE ? OR site_physical LIKE ?)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
            
        if zone:
            query_parts.append("zone = ?")
            params.append(zone)
            
        if olt:
            query_parts.append("olt = ?")
            params.append(olt)
            
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
            
        if box_class:
            query_parts.append("box_class = ?")
            params.append(box_class)
            
        if site_logical:
            query_parts.append("site_logical LIKE ?")
            params.append(f"%{site_logical}%")
            
        where_clause = " AND ".join(query_parts)
        
        cursor.execute(f"SELECT COUNT(*) FROM boxes {where_clause}", params)
        total_count = cursor.fetchone()[0]
        
        allowed_sort_cols = ["node_code", "zone", "branch", "status_service", "site_physical", "site_logical", "olt", "box_class", "box_type", "update_time"]
        if sort_by not in allowed_sort_cols:
            sort_by = "node_code"
        if sort_dir.upper() not in ["ASC", "DESC"]:
            sort_dir = "ASC"
            
        offset = (page - 1) * per_page
        query = f"""
            SELECT * FROM boxes 
            {where_clause} 
            ORDER BY {sort_by} {sort_dir} 
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [per_page, offset])
        rows = cursor.fetchall()
        boxes_list = [dict(r) for r in rows]
        
        conn.close()
        return {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "pages": (total_count + per_page - 1) // per_page,
            "data": boxes_list
        }

    @classmethod
    def get_nearest_boxes(cls, lat, lng, limit=12):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *, distance(latitude, longitude, ?, ?) AS dist_meters
            FROM boxes
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0 AND longitude != 0
            ORDER BY dist_meters ASC
            LIMIT ?
        """, (lat, lng, limit))
        rows = cursor.fetchall()
        boxes_list = [dict(r) for r in rows]
        conn.close()
        return boxes_list

    @classmethod
    def get_box(cls, box_id):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM boxes WHERE id = ?", (box_id,))
        row = cursor.fetchone()
        box_data = dict(row) if row else None
        conn.close()
        return box_data

    @classmethod
    def add_box(cls, data):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        columns = [
            "branch", "zone", "infrastructure", "note", "status_service", "site_physical", "site_logical",
            "olt", "node_code", "box_class", "box_type", "department", "latitude", "longitude",
            "port_used", "update_time"
        ]
        
        insert_cols = []
        insert_vals = []
        placeholders = []
        
        for col in columns:
            if col in data:
                insert_cols.append(col)
                if col in ["latitude", "longitude"] and data[col] is not None:
                    try:
                        insert_vals.append(float(data[col]))
                    except ValueError:
                        insert_vals.append(None)
                else:
                    insert_vals.append(data[col])
                placeholders.append("?")
                
        # Mark as locally modified
        insert_cols.append("locally_modified")
        insert_vals.append(1)
        placeholders.append("?")
                
        query = f"INSERT INTO boxes ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(query, insert_vals)
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id

    @classmethod
    def update_box(cls, box_id, data):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        columns = [
            "branch", "zone", "infrastructure", "note", "status_service", "site_physical", "site_logical",
            "olt", "node_code", "box_class", "box_type", "department", "latitude", "longitude",
            "port_used", "update_time"
        ]
        
        update_pairs = []
        update_vals = []
        
        for col in columns:
            if col in data:
                update_pairs.append(f"{col} = ?")
                if col in ["latitude", "longitude"] and data[col] is not None:
                    try:
                        update_vals.append(float(data[col]))
                    except ValueError:
                        update_vals.append(None)
                else:
                    update_vals.append(data[col])
                    
        if not update_pairs:
            conn.close()
            return False
            
        # Mark as locally modified
        update_pairs.append("locally_modified = 1")
        query = f"UPDATE boxes SET {', '.join(update_pairs)} WHERE id = ?"
        update_vals.append(box_id)
        
        cursor.execute(query, update_vals)
        conn.commit()
        changes = conn.total_changes > 0
        conn.close()
        return changes

    @classmethod
    def delete_box(cls, box_id):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM boxes WHERE id = ?", (box_id,))
        conn.commit()
        changes = conn.total_changes > 0
        conn.close()
        return changes

    # ==========================================
    # STAFF CRUD METHODS (JOIN OF ASSIGNMENTS & STAFF)
    # ==========================================
    @classmethod
    def get_staff(cls, page=1, per_page=15, search="", branch="", partner="", sort_by="staff_team", sort_dir="ASC"):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE 1=1"]
        params = []
        
        if search:
            query_parts.append("(za.team_distribution LIKE ? OR s.vtp_username LIKE ? OR za.zone LIKE ? OR za.olt LIKE ?)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
            
        if branch:
            query_parts.append("za.branch = ?")
            params.append(branch)
            
        if partner:
            query_parts.append("za.partner = ?")
            params.append(partner)
            
        where_clause = " AND ".join(query_parts)
        
        # Get count
        cursor.execute(f"SELECT COUNT(*) FROM zone_assignments za LEFT JOIN staff s ON LOWER(TRIM(s.staff_team)) = LOWER(TRIM(za.team_distribution)) {where_clause}", params)
        total_count = cursor.fetchone()[0]
        
        # Allowed sorting columns
        allowed_sort_cols = {
            "staff_team": "za.team_distribution",
            "zone": "za.zone",
            "branch": "za.branch",
            "partner": "za.partner",
            "vtp_username": "s.vtp_username",
            "olt": "za.olt",
            "partner_incidence": "za.incidents_distribution_by_team"
        }
        
        sort_col = allowed_sort_cols.get(sort_by, "za.team_distribution")
        if sort_dir.upper() not in ["ASC", "DESC"]:
            sort_dir = "ASC"
            
        offset = (page - 1) * per_page
        query = f"""
            SELECT 
                za.id,
                za.zone,
                za.branch,
                za.partner,
                za.olt,
                za.site,
                za.team_distribution as staff_team,
                za.incidents_distribution_by_team as partner_incidence,
                za.incidents_distribution,
                s.vtp_username,
                s.warranty_period
            FROM zone_assignments za
            LEFT JOIN staff s ON LOWER(TRIM(s.staff_team)) = LOWER(TRIM(za.team_distribution))
            {where_clause}
            ORDER BY {sort_col} {sort_dir}
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [per_page, offset])
        rows = cursor.fetchall()
        staff_list = [dict(r) for r in rows]
        
        conn.close()
        return {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "pages": (total_count + per_page - 1) // per_page,
            "data": staff_list
        }

    @classmethod
    def get_staff_member(cls, assignment_id):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                za.id,
                za.zone,
                za.branch,
                za.partner,
                za.olt,
                za.site,
                za.team_distribution as staff_team,
                za.incidents_distribution_by_team as partner_incidence,
                za.incidents_distribution,
                s.vtp_username,
                s.warranty_period
            FROM zone_assignments za
            LEFT JOIN staff s ON LOWER(TRIM(s.staff_team)) = LOWER(TRIM(za.team_distribution))
            WHERE za.id = ?
        """, (assignment_id,))
        row = cursor.fetchone()
        staff_data = dict(row) if row else None
        conn.close()
        return staff_data

    @classmethod
    def add_staff(cls, data):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # 1. Insert into staff list first (if not exists or update)
        cursor.execute("""
            INSERT INTO staff (branch, staff_team, warranty_period, partner, vtp_username, locally_modified)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(staff_team) DO UPDATE SET
                warranty_period = excluded.warranty_period,
                vtp_username = excluded.vtp_username,
                partner = excluded.partner,
                branch = excluded.branch,
                locally_modified = 1
        """, (
            data.get("branch"),
            data.get("staff_team"),
            data.get("warranty_period"),
            data.get("partner"),
            data.get("vtp_username")
        ))
        
        # 2. Insert into zone_assignments
        cursor.execute("""
            INSERT INTO zone_assignments (zone, site, olt, branch, partner, team_distribution, incidents_distribution, incidents_distribution_by_team, locally_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            data.get("zone"),
            data.get("site"),
            data.get("olt"),
            data.get("branch"),
            data.get("partner"),
            data.get("staff_team"),
            data.get("incidents_distribution"),
            data.get("partner_incidence")
        ))
        
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id

    @classmethod
    def update_staff(cls, assignment_id, data):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # Get old assignment to know if team distribution changed
        cursor.execute("SELECT team_distribution FROM zone_assignments WHERE id = ?", (assignment_id,))
        old_row = cursor.fetchone()
        old_team = old_row["team_distribution"] if old_row else None
        
        # 1. Update zone_assignments
        cursor.execute("""
            UPDATE zone_assignments
            SET zone = ?, site = ?, olt = ?, branch = ?, partner = ?, team_distribution = ?, 
                incidents_distribution = ?, incidents_distribution_by_team = ?, locally_modified = 1
            WHERE id = ?
        """, (
            data.get("zone"),
            data.get("site"),
            data.get("olt"),
            data.get("branch"),
            data.get("partner"),
            data.get("staff_team"),
            data.get("incidents_distribution"),
            data.get("partner_incidence"),
            assignment_id
        ))
        
        # 2. Update staff profile
        staff_team = data.get("staff_team")
        cursor.execute("""
            INSERT INTO staff (branch, staff_team, warranty_period, partner, vtp_username, locally_modified)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(staff_team) DO UPDATE SET
                warranty_period = excluded.warranty_period,
                vtp_username = excluded.vtp_username,
                partner = excluded.partner,
                branch = excluded.branch,
                locally_modified = 1
        """, (
            data.get("branch"),
            staff_team,
            data.get("warranty_period"),
            data.get("partner"),
            data.get("vtp_username")
        ))
        
        conn.commit()
        conn.close()
        return True

    @classmethod
    def delete_staff(cls, assignment_id):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM zone_assignments WHERE id = ?", (assignment_id,))
        conn.commit()
        changes = cursor.rowcount > 0
        conn.close()
        return changes

    @classmethod
    def export_staff_csv(cls):
        import io
        import csv
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                za.id,
                za.team_distribution as staff_team,
                za.zone,
                za.branch,
                za.partner,
                s.vtp_username,
                za.olt,
                za.incidents_distribution_by_team as partner_incidence,
                za.site,
                za.incidents_distribution,
                s.warranty_period
            FROM zone_assignments za
            LEFT JOIN staff s ON LOWER(TRIM(s.staff_team)) = LOWER(TRIM(za.team_distribution))
            ORDER BY za.id ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n')
        writer.writerow([
            "id", "staff_team", "zone", "branch", "partner", "vtp_username", 
            "olt", "partner_incidence", "site", "incidents_distribution", "warranty_period"
        ])
        
        for r in rows:
            writer.writerow([
                r["id"],
                r["staff_team"] or "",
                r["zone"] or "",
                r["branch"] or "",
                r["partner"] or "",
                r["vtp_username"] or "",
                r["olt"] or "",
                r["partner_incidence"] or "",
                r["site"] or "",
                r["incidents_distribution"] or "",
                r["warranty_period"] if r["warranty_period"] is not None else ""
            ])
            
        return output.getvalue()

    @classmethod
    def import_staff_csv(cls, csv_content):
        import io
        import csv
        
        if isinstance(csv_content, bytes):
            try:
                csv_text = csv_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                csv_text = csv_content.decode('latin-1')
        else:
            csv_text = csv_content
            
        # Determinar delimitador (punto y coma o coma)
        delimiter = ','
        first_line = csv_text.split('\n')[0] if csv_text else ""
        if ';' in first_line:
            delimiter = ';'
            
        f = io.StringIO(csv_text)
        reader = csv.DictReader(f, delimiter=delimiter)
        
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        created_count = 0
        updated_count = 0
        error_list = []
        
        for idx, row in enumerate(reader):
            staff_team = row.get("staff_team", "").strip()
            zone = row.get("zone", "").strip()
            
            if not staff_team or not zone:
                error_list.append(f"Fila {idx+2}: 'staff_team' y 'zone' son obligatorios.")
                continue
                
            branch = row.get("branch", "").strip()
            partner = row.get("partner", "").strip()
            vtp_username = row.get("vtp_username", "").strip()
            olt = row.get("olt", "").strip()
            partner_incidence = row.get("partner_incidence", "").strip()
            site = row.get("site", "").strip()
            incidents_distribution = row.get("incidents_distribution", "").strip()
            
            warranty_period = row.get("warranty_period", "").strip()
            try:
                warranty_period = int(float(warranty_period)) if warranty_period else None
            except ValueError:
                warranty_period = None
                
            row_id = row.get("id", "").strip()
            
            try:
                assignment_exists = False
                if row_id:
                    cursor.execute("SELECT id FROM zone_assignments WHERE id = ?", (row_id,))
                    if cursor.fetchone():
                        assignment_exists = True
                        
                if assignment_exists:
                    # Actualizar zone_assignments
                    cursor.execute("""
                        UPDATE zone_assignments
                        SET zone = ?, site = ?, olt = ?, branch = ?, partner = ?, team_distribution = ?, 
                            incidents_distribution = ?, incidents_distribution_by_team = ?, locally_modified = 1
                        WHERE id = ?
                    """, (zone, site, olt, branch, partner, staff_team, incidents_distribution, partner_incidence, row_id))
                    
                    # Actualizar o insertar perfil en staff
                    cursor.execute("""
                        INSERT INTO staff (branch, staff_team, warranty_period, partner, vtp_username, locally_modified)
                        VALUES (?, ?, ?, ?, ?, 1)
                        ON CONFLICT(staff_team) DO UPDATE SET
                            warranty_period = excluded.warranty_period,
                            vtp_username = excluded.vtp_username,
                            partner = excluded.partner,
                            branch = excluded.branch,
                            locally_modified = 1
                    """, (branch, staff_team, warranty_period, partner, vtp_username))
                    
                    updated_count += 1
                else:
                    # Crear nuevo zone_assignments
                    cursor.execute("""
                        INSERT INTO zone_assignments (zone, site, olt, branch, partner, team_distribution, incidents_distribution, incidents_distribution_by_team, locally_modified)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (zone, site, olt, branch, partner, staff_team, incidents_distribution, partner_incidence))
                    
                    # Actualizar o insertar perfil en staff
                    cursor.execute("""
                        INSERT INTO staff (branch, staff_team, warranty_period, partner, vtp_username, locally_modified)
                        VALUES (?, ?, ?, ?, ?, 1)
                        ON CONFLICT(staff_team) DO UPDATE SET
                            warranty_period = excluded.warranty_period,
                            vtp_username = excluded.vtp_username,
                            partner = excluded.partner,
                            branch = excluded.branch,
                            locally_modified = 1
                    """, (branch, staff_team, warranty_period, partner, vtp_username))
                    
                    created_count += 1
            except Exception as e:
                error_list.append(f"Fila {idx+2} (Error SQL): {str(e)}")
                
        conn.commit()
        conn.close()
        return created_count, updated_count, error_list

    @classmethod
    def get_partner_capacity_report(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                pc.id,
                pc.branch,
                pc.partner,
                pc.teams_total,
                pc.ft_total,
                pc.teams_deploy,
                pc.teams_incidents,
                pc.teams_odn,
                (
                    SELECT COUNT(DISTINCT za.zone) 
                    FROM zone_assignments za 
                    WHERE LOWER(TRIM(za.partner)) = LOWER(TRIM(pc.partner)) 
                      AND LOWER(TRIM(za.branch)) = LOWER(TRIM(pc.branch))
                ) as assigned_zones,
                (
                    SELECT COUNT(DISTINCT za.olt) 
                    FROM zone_assignments za 
                    WHERE LOWER(TRIM(za.partner)) = LOWER(TRIM(pc.partner)) 
                      AND LOWER(TRIM(za.branch)) = LOWER(TRIM(pc.branch))
                ) as assigned_olts,
                (
                    SELECT SUM(z.active_customers) 
                    FROM zone_assignments za
                    JOIN zones z ON LOWER(TRIM(z.zone)) = LOWER(TRIM(za.zone))
                    WHERE LOWER(TRIM(za.partner)) = LOWER(TRIM(pc.partner)) 
                      AND LOWER(TRIM(za.branch)) = LOWER(TRIM(pc.branch))
                ) as total_active_customers,
                (
                    SELECT AVG(z.percent_saturation) 
                    FROM zone_assignments za
                    JOIN zones z ON LOWER(TRIM(z.zone)) = LOWER(TRIM(za.zone))
                    WHERE LOWER(TRIM(za.partner)) = LOWER(TRIM(pc.partner)) 
                      AND LOWER(TRIM(za.branch)) = LOWER(TRIM(pc.branch))
                ) as avg_saturation
            FROM partner_capacities pc
            ORDER BY pc.partner ASC, pc.branch ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            d = dict(r)
            if d["avg_saturation"] is not None:
                d["avg_saturation_percent"] = round(d["avg_saturation"] * 100, 2)
            else:
                d["avg_saturation_percent"] = 0.0
            result.append(d)
            
        return result

    @classmethod
    def get_zone_capacity_detail(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                z.id as zone_id,
                z.zone,
                z.branch,
                z.active_customers,
                z.saturation as saturation_ports,
                z.percent_saturation as saturation_clients,
                z.percent_cancel as cancel_rate,
                za.partner as partner_deploy,
                pc.teams_deploy as partner_teams_deploy
            FROM zones z
            LEFT JOIN zone_assignments za ON LOWER(TRIM(za.zone)) = LOWER(TRIM(z.zone))
            LEFT JOIN partner_capacities pc ON LOWER(TRIM(pc.partner)) = LOWER(TRIM(za.partner)) 
                                           AND LOWER(TRIM(pc.branch)) = LOWER(TRIM(z.branch))
            WHERE z.zone IS NOT NULL AND z.zone != ''
            ORDER BY z.percent_saturation DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            d = dict(r)
            if d["saturation_ports"] is not None:
                d["saturation_ports_percent"] = round(d["saturation_ports"] * 100, 2)
            else:
                d["saturation_ports_percent"] = 0.0
                
            if d["saturation_clients"] is not None:
                d["saturation_clients_percent"] = round(d["saturation_clients"] * 100, 2)
            else:
                d["saturation_clients_percent"] = 0.0
                
            if d["cancel_rate"] is not None:
                d["cancel_rate_percent"] = round(d["cancel_rate"] * 100, 2)
            else:
                d["cancel_rate_percent"] = 0.0
                
            teams = d["partner_teams_deploy"]
            active = d["active_customers"] or 0
            if teams and teams > 0:
                d["clients_per_team"] = round(active / teams, 1)
            else:
                d["clients_per_team"] = None
                
            result.append(d)
            
        return result

    @classmethod
    def get_branch_capacity_stacked_report(cls, branch="", partner="", zone=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # 1. Drill-down: Partner Filter Active -> Show sites of that partner
        if partner:
            query_parts = ["LOWER(TRIM(za.partner)) = LOWER(TRIM(?))"]
            params = [partner]
            if branch:
                query_parts.append("LOWER(TRIM(z.branch)) = LOWER(TRIM(?))")
                params.append(branch)
            where_clause = " AND ".join(query_parts)
            query = f"""
                SELECT 
                    z.site_physical as branch,
                    SUM(COALESCE(z.qty_ports_box, 0)) as total_ports,
                    SUM(COALESCE(z.active_customers, 0)) as active,
                    SUM(COALESCE(z.suspended_customers, 0)) as suspended,
                    SUM(COALESCE(z.canceled_customers, 0)) as canceled
                FROM zones z
                JOIN (
                    SELECT DISTINCT LOWER(TRIM(zone)) as zone, partner
                    FROM zone_assignments
                    WHERE partner IS NOT NULL AND partner != ''
                ) za ON za.zone = LOWER(TRIM(z.zone))
                WHERE {where_clause}
                GROUP BY z.site_physical
                ORDER BY total_ports DESC
            """
            cursor.execute(query, params)

        # 2. Drill-down: Branch Filter Active -> Show partners of that branch
        elif branch:
            query = """
                SELECT 
                    za.partner as branch,
                    SUM(COALESCE(z.qty_ports_box, 0)) as total_ports,
                    SUM(COALESCE(z.active_customers, 0)) as active,
                    SUM(COALESCE(z.suspended_customers, 0)) as suspended,
                    SUM(COALESCE(z.canceled_customers, 0)) as canceled
                FROM zones z
                JOIN (
                    SELECT DISTINCT LOWER(TRIM(zone)) as zone, partner
                    FROM zone_assignments
                    WHERE partner IS NOT NULL AND partner != ''
                ) za ON za.zone = LOWER(TRIM(z.zone))
                WHERE LOWER(TRIM(z.branch)) = LOWER(TRIM(?))
                GROUP BY za.partner
                ORDER BY total_ports DESC
            """
            cursor.execute(query, (branch,))

        # 3. Default: No filter -> Show all branches
        else:
            query = """
                SELECT 
                    z.branch,
                    SUM(COALESCE(z.qty_ports_box, 0)) as total_ports,
                    SUM(COALESCE(z.active_customers, 0)) as active,
                    SUM(COALESCE(z.suspended_customers, 0)) as suspended,
                    SUM(COALESCE(z.canceled_customers, 0)) as canceled
                FROM zones z
                WHERE z.branch IS NOT NULL AND z.branch != ''
                GROUP BY z.branch
                ORDER BY total_ports DESC
            """
            cursor.execute(query)

        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            d = dict(r)
            total = d["total_ports"] or 0
            act = d["active"] or 0
            susp = d["suspended"] or 0
            canc = d["canceled"] or 0
            
            if total < (act + susp + canc):
                total = act + susp + canc
                
            free = total - (act + susp + canc)
            if free < 0:
                free = 0
                
            d["free_ports"] = free
            d["total_ports"] = total
            
            if total > 0:
                d["active_pct"] = round((act / total) * 100, 2)
                d["suspended_pct"] = round((susp / total) * 100, 2)
                d["canceled_pct"] = round((canc / total) * 100, 2)
                d["free_pct"] = round((free / total) * 100, 2)
            else:
                d["active_pct"] = 0.0
                d["suspended_pct"] = 0.0
                d["canceled_pct"] = 0.0
                d["free_pct"] = 0.0
                
            result.append(d)
            
        return result

    @classmethod
    def get_incidents_by_month(cls, branch="", month="", site="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        group_col = "week_number" if week else "month_year"
        query_parts = [f"{group_col} IS NOT NULL AND {group_col} != ''"]
        params = []
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
        if week:
            query_parts.append("week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("month_year = ?")
            params.append(month)
        if site:
            query_parts.append("station_code = ?")
            params.append(site)
            
        where_clause = "WHERE " + " AND ".join(query_parts)
        
        query = f"""
            SELECT 
                {group_col} as month_year,
                COUNT(*) as total_incidents,
                COUNT(DISTINCT subscriber) as unique_clients
            FROM incidents
            {where_clause}
            GROUP BY {group_col}
            ORDER BY {group_col} ASC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @classmethod
    def get_incidents_by_status(cls, branch="", month="", site="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["status_desc IS NOT NULL AND status_desc != ''"]
        params = []
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
        if week:
            query_parts.append("week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("month_year = ?")
            params.append(month)
        if site:
            query_parts.append("station_code = ?")
            params.append(site)
            
        where_clause = "WHERE " + " AND ".join(query_parts)
        
        total_query = f"SELECT COUNT(*) FROM incidents {where_clause}"
        cursor.execute(total_query, params)
        total_count = cursor.fetchone()[0] or 1
        
        query = f"""
            SELECT 
                status_desc,
                COUNT(*) as count
            FROM incidents
            {where_clause}
            GROUP BY status_desc
            ORDER BY count DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            d = dict(r)
            d["percentage"] = round((d["count"] * 100.0) / total_count, 2)
            result.append(d)
        return result

    @classmethod
    def get_incidents_sites(cls, branch=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        if branch:
            cursor.execute("""
                SELECT DISTINCT station_code 
                FROM incidents 
                WHERE branch = ? AND station_code IS NOT NULL AND station_code != '' 
                ORDER BY station_code
            """, (branch,))
        else:
            cursor.execute("""
                SELECT DISTINCT station_code 
                FROM incidents 
                WHERE station_code IS NOT NULL AND station_code != '' 
                ORDER BY station_code
            """)
        rows = cursor.fetchall()
        conn.close()
        return [r["station_code"] for r in rows]

    @classmethod
    def get_incidents_sites_ranking(cls, branch="", month="", site="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["station_code IS NOT NULL AND station_code != ''"]
        params = []
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
        if week:
            query_parts.append("week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("month_year = ?")
            params.append(month)
        if site:
            query_parts.append("station_code = ?")
            params.append(site)
            
        where_clause = "WHERE " + " AND ".join(query_parts)
        
        query = f"""
            SELECT 
                station_code as site,
                COUNT(*) as total_incidents,
                COUNT(DISTINCT subscriber) as unique_clients
            FROM incidents
            {where_clause}
            GROUP BY station_code
            ORDER BY total_incidents DESC
            LIMIT 15
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @classmethod
    def get_incidents_months(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT month_year 
            FROM incidents 
            WHERE month_year IS NOT NULL AND month_year != '' 
            ORDER BY month_year ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [r["month_year"] for r in rows]

    @classmethod
    def get_incidents_monthly_breakdown(cls, branch="", month="", site="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        group_col = "week_number" if week else "month_year"
        query_parts = [f"{group_col} IS NOT NULL AND {group_col} != ''"]
        params = []
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
        if week:
            query_parts.append("week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("month_year = ?")
            params.append(month)
        if site:
            query_parts.append("station_code = ?")
            params.append(site)
        where_clause = "WHERE " + " AND ".join(query_parts)
        
        query = f"""
            SELECT 
                {group_col} as month_year,
                status_desc,
                COUNT(*) as count
            FROM incidents
            {where_clause}
            GROUP BY {group_col}, status_desc
            ORDER BY {group_col} ASC, count DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @classmethod
    def get_incidents_site_breakdown(cls, branch="", month="", site="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["station_code IS NOT NULL AND station_code != ''"]
        params = []
        if branch:
            query_parts.append("branch = ?")
            params.append(branch)
        if week:
            query_parts.append("week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("month_year = ?")
            params.append(month)
        if site:
            query_parts.append("station_code = ?")
            params.append(site)
        where_clause = "WHERE " + " AND ".join(query_parts)
        
        top_sites_query = f"""
            SELECT station_code, COUNT(*) as total
            FROM incidents
            {where_clause}
            GROUP BY station_code
            ORDER BY total DESC
            LIMIT 10
        """
        cursor.execute(top_sites_query, params)
        top_sites = [r["station_code"] for r in cursor.fetchall()]
        
        if not top_sites:
            conn.close()
            return []
            
        placeholders = ", ".join(["?"] * len(top_sites))
        query = f"""
            SELECT 
                station_code,
                status_desc,
                COUNT(*) as count
            FROM incidents
            {where_clause} AND station_code IN ({placeholders})
            GROUP BY station_code, status_desc
            ORDER BY station_code ASC, count DESC
        """
        cursor.execute(query, params + top_sites)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @classmethod
    def get_site_outages_report(cls, branch="", month="", site="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE 1=1"]
        params = []
        
        if branch:
            query_parts.append("COALESCE(z.branch, i_br.branch) = ?")
            params.append(branch)
        if week:
            query_parts.append("o.week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("o.month_year = ?")
            params.append(month)
        if site:
            query_parts.append("o.site = ?")
            params.append(site)
            
        where_clause = " AND ".join(query_parts)
        
        period_col_olt = "o.week_number" if week else "o.month_year"
        period_col_sub = "o_sub.week_number" if week else "o_sub.month_year"
        
        query = f"""
            SELECT 
                o.site,
                COALESCE(z.branch, i_br.branch) as branch,
                {period_col_olt} as month_year,
                SUM(CASE WHEN o.tipo_corte = 'CORTE-ENERGIA' THEN 1 ELSE 0 END) as energy_cuts,
                SUM(CASE WHEN o.tipo_corte = 'CORTE-ENERGIA' THEN COALESCE(o.onus_afectadas, 0) ELSE 0 END) as energy_affected,
                SUM(CASE WHEN o.tipo_corte = 'CORTE-LOS' THEN 1 ELSE 0 END) as odn_cuts,
                SUM(CASE WHEN o.tipo_corte = 'CORTE-LOS' THEN COALESCE(o.onus_afectadas, 0) ELSE 0 END) as odn_affected,
                COALESCE(i.total_wos, 0) as total_wos
            FROM olt_cortes o
            LEFT JOIN (
                SELECT DISTINCT site_physical as site, branch FROM zones WHERE site_physical IS NOT NULL
                UNION
                SELECT DISTINCT site_logical as site, branch FROM zones WHERE site_logical IS NOT NULL
            ) z ON LOWER(TRIM(z.site)) = LOWER(TRIM(o.site))
            LEFT JOIN (
                SELECT DISTINCT station_code as site, branch FROM incidents WHERE station_code IS NOT NULL
            ) i_br ON LOWER(TRIM(i_br.site)) = LOWER(TRIM(o.site))
            LEFT JOIN (
                SELECT 
                    o_sub.site,
                    {period_col_sub} as period,
                    COUNT(DISTINCT i.id) as total_wos
                FROM olt_cortes o_sub
                JOIN incidents i ON i.station_code = o_sub.site
                WHERE i.create_time >= o_sub.hora_corte 
                  AND i.create_time <= datetime(o_sub.hora_corte, '+24 hours')
                GROUP BY o_sub.site, {period_col_sub}
            ) i ON i.site = o.site AND i.period = {period_col_olt}
            {where_clause}
            GROUP BY o.site, {period_col_olt}
            ORDER BY (COUNT(o.id)) DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            d = dict(r)
            result.append(d)
            
        return result

    @classmethod
    def get_site_outage_causes(cls, branch="", month="", site="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE 1=1"]
        params = []
        
        if branch:
            query_parts.append("COALESCE(z.branch, i_br.branch) = ?")
            params.append(branch)
        if week:
            query_parts.append("o.week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("o.month_year = ?")
            params.append(month)
        if site:
            query_parts.append("o.site = ?")
            params.append(site)
            
        where_clause = " AND ".join(query_parts)
        
        query = f"""
            SELECT 
                o.causa,
                COUNT(DISTINCT o.site) as unique_sites,
                COUNT(o.id) as total_cuts,
                SUM(COALESCE(o.onus_afectadas, 0)) as total_affected_onus
            FROM olt_cortes o
            LEFT JOIN (
                SELECT DISTINCT site_physical as site, branch FROM zones WHERE site_physical IS NOT NULL
                UNION
                SELECT DISTINCT site_logical as site, branch FROM zones WHERE site_logical IS NOT NULL
            ) z ON LOWER(TRIM(z.site)) = LOWER(TRIM(o.site))
            LEFT JOIN (
                SELECT DISTINCT station_code as site, branch FROM incidents WHERE station_code IS NOT NULL
            ) i_br ON LOWER(TRIM(i_br.site)) = LOWER(TRIM(o.site))
            {where_clause}
            GROUP BY o.causa
            ORDER BY total_affected_onus DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @classmethod
    def get_site_outage_details(cls, site, branch="", month="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE LOWER(TRIM(o.site)) = LOWER(TRIM(?))"]
        params = [site]
        
        if branch:
            query_parts.append("COALESCE(z.branch, i_br.branch) = ?")
            params.append(branch)
        if week:
            query_parts.append("o.week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("o.month_year = ?")
            params.append(month)
            
        where_clause = " AND ".join(query_parts)
        
        query = f"""
            SELECT 
                o.olt_name,
                o.pon,
                o.tipo_corte,
                o.hora_corte,
                o.onus_afectadas,
                o.causa,
                o.onus_ids,
                (
                    SELECT COUNT(DISTINCT inc.id)
                    FROM incidents inc
                    WHERE inc.station_code = o.site
                      AND inc.create_time >= o.hora_corte
                      AND inc.create_time <= datetime(o.hora_corte, '+24 hours')
                ) as wos_created
            FROM olt_cortes o
            LEFT JOIN (
                SELECT DISTINCT site_physical as site, branch FROM zones WHERE site_physical IS NOT NULL
                UNION
                SELECT DISTINCT site_logical as site, branch FROM zones WHERE site_logical IS NOT NULL
            ) z ON LOWER(TRIM(z.site)) = LOWER(TRIM(o.site))
            LEFT JOIN (
                SELECT DISTINCT station_code as site, branch FROM incidents WHERE station_code IS NOT NULL
            ) i_br ON LOWER(TRIM(i_br.site)) = LOWER(TRIM(o.site))
            {where_clause}
            ORDER BY o.hora_corte DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @classmethod
    def get_site_wo_details(cls, site, branch="", month="", week=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE i.station_code = ?"]
        params = [site]
        
        if week:
            query_parts.append("o.week_number = ?")
            params.append(week)
        elif month:
            query_parts.append("o.month_year = ?")
            params.append(month)
            
        where_clause = " AND ".join(query_parts)
        
        query = f"""
            SELECT DISTINCT
                i.wo_code,
                i.subscriber,
                i.create_time,
                i.partner_close,
                i.qty_repeat,
                i.status_desc
            FROM incidents i
            JOIN olt_cortes o ON o.site = i.station_code
            {where_clause}
              AND i.create_time >= o.hora_corte
              AND i.create_time <= datetime(o.hora_corte, '+24 hours')
            ORDER BY i.create_time DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @classmethod
    def get_incidents_weeks(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT DISTINCT week_number FROM olt_cortes WHERE week_number IS NOT NULL AND week_number != ''
            UNION
            SELECT DISTINCT week_number FROM incidents WHERE week_number IS NOT NULL AND week_number != ''
            ORDER BY week_number DESC
        """
        cursor.execute(query)
        weeks = [r[0] for r in cursor.fetchall()]
        conn.close()
        return weeks


    @classmethod
    def get_deployments_report(cls, branch="", month=""):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        where_parts = []
        params = []
        if branch:
            where_parts.append("branch = ?")
            params.append(branch)
        if month:
            where_parts.append("month_year = ?")
            params.append(month)
            
        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)
            
        # Get distinct months to calculate days count
        cursor.execute(f"SELECT DISTINCT month_year FROM deployments {where_clause}", params)
        unique_months = [r["month_year"] for r in cursor.fetchall() if r["month_year"] and r["month_year"].strip().lower() != 'pending']
        
        def get_days_in_month_year(my):
            if not my or '/' not in my:
                return 30
            parts = my.split('/')
            try:
                m = int(parts[0])
                if m in (1, 3, 5, 7, 8, 10, 12):
                    return 31
                elif m == 2:
                    return 28
                else:
                    return 30
            except ValueError:
                return 30
                
        if month:
            total_days = get_days_in_month_year(month)
        else:
            total_days = sum(get_days_in_month_year(m) for m in unique_months)
            if total_days == 0:
                total_days = 30
                
        query = f"""
            SELECT 
                partner,
                branch,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN kpi_from_paid = '<24H' THEN 1 ELSE 0 END) as tasks_24h,
                SUM(CASE WHEN kpi_from_paid IN ('<24H', '<48H') THEN 1 ELSE 0 END) as tasks_48h,
                SUM(CASE WHEN kpi_from_paid IN ('<24H', '<48H', '<72H') THEN 1 ELSE 0 END) as tasks_72h,
                SUM(close_time_hrs) as sum_close_time,
                COUNT(close_time_hrs) as count_close_time
            FROM deployments
            {where_clause}
            GROUP BY partner, branch
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        cursor.execute("SELECT branch, partner, teams_deploy, ft_total FROM partner_capacities")
        capacities = {}
        for r in cursor.fetchall():
            br_val = r["branch"] or ""
            p_val = r["partner"] or ""
            key = (br_val.upper().strip(), p_val.upper().strip())
            capacities[key] = {
                "teams_deploy": r["teams_deploy"] or 0,
                "ft_total": r["ft_total"] or 0
            }
            
        cursor.execute("SELECT branch, partner, COUNT(DISTINCT zone) as zones_count FROM zone_assignments GROUP BY branch, partner")
        zones_assigned = {}
        for r in cursor.fetchall():
            br_val = r["branch"] or ""
            p_val = r["partner"] or ""
            key = (br_val.upper().strip(), p_val.upper().strip())
            zones_assigned[key] = r["zones_count"] or 0
            
        def normalize_p(p):
            if not p or p == "nan": return ""
            p = str(p).upper().strip()
            p = p.replace("L&P", "L Y P")
            p = p.replace("JLFLOWERS", "JFLOWERS")
            if p.startswith("BITEL"):
                return "BITEL"
            return p
            
        def get_matching_capacity(br, part):
            br_norm = str(br).upper().strip()
            p_norm = normalize_p(part)
            for (c_br, c_p), cap in capacities.items():
                if c_br == br_norm and normalize_p(c_p) == p_norm:
                    return cap
            return {"teams_deploy": 0, "ft_total": 0}
            
        def get_matching_zones(br, part):
            br_norm = str(br).upper().strip()
            p_norm = normalize_p(part)
            total_zones = 0
            for (z_br, z_p), count in zones_assigned.items():
                if z_br == br_norm and normalize_p(z_p) == p_norm:
                    total_zones += count
            return total_zones

        detail_table = []
        for r in rows:
            p = r["partner"]
            b = r["branch"]
            if not p or p == "nan":
                continue
                
            cap = get_matching_capacity(b, p)
            zones_count = get_matching_zones(b, p)
            
            # Check if partner belongs to this branch (capacity or zone assignment record)
            br_norm = str(b).upper().strip()
            p_norm = normalize_p(p)
            
            has_capacity_record = False
            for (c_br, c_p) in capacities.keys():
                if c_br == br_norm and normalize_p(c_p) == p_norm:
                    has_capacity_record = True
                    break
                    
            has_zones = zones_count > 0
            
            if not has_capacity_record and not has_zones:
                continue
                
            tasks = r["total_tasks"] or 0
            t24 = r["tasks_24h"] or 0
            t48 = r["tasks_48h"] or 0
            t72 = r["tasks_72h"] or 0
            sum_ct = r["sum_close_time"] or 0.0
            count_ct = r["count_close_time"] or 0
            
            sla_24 = round((t24 * 100.0) / tasks, 2) if tasks > 0 else 0.0
            sla_48 = round((t48 * 100.0) / tasks, 2) if tasks > 0 else 0.0
            sla_72 = round((t72 * 100.0) / tasks, 2) if tasks > 0 else 0.0
            
            teams = cap["teams_deploy"] or 0
            ft = cap["ft_total"] or 0
            
            tasks_per_team = round(tasks / teams, 1) if teams > 0 else None
            zones_per_team = round(zones_count / teams, 1) if teams > 0 else None
            techs_per_zone = round(ft / zones_count, 1) if zones_count > 0 else None
            
            avg_close_time_hrs = round(sum_ct / count_ct, 1) if count_ct > 0 else None
            deployments_per_day_per_team = round((tasks / total_days) / teams, 2) if (teams > 0 and total_days > 0) else None
            
            detail_table.append({
                "partner": p,
                "branch": b,
                "total_tasks": tasks,
                "tasks_24h": t24,
                "tasks_48h": t48,
                "tasks_72h": t72,
                "sla_24h_pct": sla_24,
                "sla_48h_pct": sla_48,
                "sla_72h_pct": sla_72,
                "teams_deploy": teams,
                "ft_total": ft,
                "assigned_zones": zones_count,
                "tasks_per_team": tasks_per_team,
                "zones_per_team": zones_per_team,
                "techs_per_zone": techs_per_zone,
                "sum_close_time": sum_ct,
                "count_close_time": count_ct,
                "avg_close_time_hrs": avg_close_time_hrs,
                "deployments_per_day_per_team": deployments_per_day_per_team
            })
            
        partner_agg = {}
        for row in detail_table:
            p = row["partner"]
            if p not in partner_agg:
                partner_agg[p] = {
                    "partner": p,
                    "total_tasks": 0,
                    "tasks_24h": 0,
                    "tasks_48h": 0,
                    "tasks_72h": 0,
                    "teams_deploy": 0,
                    "ft_total": 0,
                    "assigned_zones": 0,
                    "sum_close_time": 0.0,
                    "count_close_time": 0
                }
            partner_agg[p]["total_tasks"] += row["total_tasks"]
            partner_agg[p]["tasks_24h"] += row["tasks_24h"]
            partner_agg[p]["tasks_48h"] += row["tasks_48h"]
            partner_agg[p]["tasks_72h"] += row["tasks_72h"]
            partner_agg[p]["teams_deploy"] += row["teams_deploy"]
            partner_agg[p]["ft_total"] += row["ft_total"]
            partner_agg[p]["assigned_zones"] += row["assigned_zones"]
            partner_agg[p]["sum_close_time"] += row["sum_close_time"]
            partner_agg[p]["count_close_time"] += row["count_close_time"]
            
        partner_stats = []
        for p, agg in partner_agg.items():
            tasks = agg["total_tasks"]
            teams = agg["teams_deploy"]
            zones = agg["assigned_zones"]
            ft = agg["ft_total"]
            sum_ct = agg["sum_close_time"]
            count_ct = agg["count_close_time"]
            
            agg["sla_24h_pct"] = round((agg["tasks_24h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
            agg["sla_48h_pct"] = round((agg["tasks_48h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
            agg["sla_72h_pct"] = round((agg["tasks_72h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
            agg["tasks_per_team"] = round(tasks / teams, 1) if teams > 0 else None
            agg["zones_per_team"] = round(zones / teams, 1) if teams > 0 else None
            agg["techs_per_zone"] = round(ft / zones, 1) if zones > 0 else None
            agg["avg_close_time_hrs"] = round(sum_ct / count_ct, 1) if count_ct > 0 else 0.0
            agg["deployments_per_day_per_team"] = round((tasks / total_days) / teams, 2) if (teams > 0 and total_days > 0) else 0.0
            partner_stats.append(agg)
            
        branch_agg = {}
        for row in detail_table:
            br = row["branch"]
            if br not in branch_agg:
                branch_agg[br] = {
                    "branch": br,
                    "total_tasks": 0,
                    "tasks_24h": 0,
                    "tasks_48h": 0,
                    "tasks_72h": 0,
                    "teams_deploy": 0,
                    "ft_total": 0,
                    "assigned_zones": 0,
                    "sum_close_time": 0.0,
                    "count_close_time": 0
                }
            branch_agg[br]["total_tasks"] += row["total_tasks"]
            branch_agg[br]["tasks_24h"] += row["tasks_24h"]
            branch_agg[br]["tasks_48h"] += row["tasks_48h"]
            branch_agg[br]["tasks_72h"] += row["tasks_72h"]
            branch_agg[br]["teams_deploy"] += row["teams_deploy"]
            branch_agg[br]["ft_total"] += row["ft_total"]
            branch_agg[br]["assigned_zones"] += row["assigned_zones"]
            branch_agg[br]["sum_close_time"] += row["sum_close_time"]
            branch_agg[br]["count_close_time"] += row["count_close_time"]
            
        branch_stats = []
        for br, agg in branch_agg.items():
            tasks = agg["total_tasks"]
            teams = agg["teams_deploy"]
            zones = agg["assigned_zones"]
            ft = agg["ft_total"]
            sum_ct = agg["sum_close_time"]
            count_ct = agg["count_close_time"]
            
            agg["sla_24h_pct"] = round((agg["tasks_24h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
            agg["sla_48h_pct"] = round((agg["tasks_48h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
            agg["sla_72h_pct"] = round((agg["tasks_72h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
            agg["tasks_per_team"] = round(tasks / teams, 1) if teams > 0 else None
            agg["zones_per_team"] = round(zones / teams, 1) if teams > 0 else None
            agg["techs_per_zone"] = round(ft / zones, 1) if zones > 0 else None
            agg["avg_close_time_hrs"] = round(sum_ct / count_ct, 1) if count_ct > 0 else 0.0
            agg["deployments_per_day_per_team"] = round((tasks / total_days) / teams, 2) if (teams > 0 and total_days > 0) else 0.0
            branch_stats.append(agg)
            
        total_tasks = sum(r["total_tasks"] for r in detail_table)
        total_24h = sum(r["tasks_24h"] for r in detail_table)
        total_48h = sum(r["tasks_48h"] for r in detail_table)
        total_72h = sum(r["tasks_72h"] for r in detail_table)
        total_sum_ct = sum(r["sum_close_time"] for r in detail_table)
        total_count_ct = sum(r["count_close_time"] for r in detail_table)
        
        overall_teams = sum(r["teams_deploy"] for r in detail_table)
        overall_techs = sum(r["ft_total"] for r in detail_table)
        overall_zones = sum(r["assigned_zones"] for r in detail_table)
        
        overall = {
            "total_tasks": total_tasks,
            "sla_24h_pct": round((total_24h * 100.0) / total_tasks, 2) if total_tasks > 0 else 0.0,
            "sla_48h_pct": round((total_48h * 100.0) / total_tasks, 2) if total_tasks > 0 else 0.0,
            "sla_72h_pct": round((total_72h * 100.0) / total_tasks, 2) if total_tasks > 0 else 0.0,
            "teams_deploy": overall_teams,
            "ft_total": overall_techs,
            "assigned_zones": overall_zones,
            "tasks_per_team": round(total_tasks / overall_teams, 1) if overall_teams > 0 else None,
            "zones_per_team": round(overall_zones / overall_teams, 1) if overall_teams > 0 else None,
            "techs_per_zone": round(overall_techs / overall_zones, 1) if overall_zones > 0 else None,
            "avg_close_time_hrs": round(total_sum_ct / total_count_ct, 1) if total_count_ct > 0 else 0.0,
            "deployments_per_day_per_team": round((total_tasks / total_days) / overall_teams, 2) if (overall_teams > 0 and total_days > 0) else 0.0
        }
        
        conn.close()
        return {
            "overall": overall,
            "partner_stats": partner_stats,
            "branch_stats": branch_stats,
            "detail_table": detail_table
        }

