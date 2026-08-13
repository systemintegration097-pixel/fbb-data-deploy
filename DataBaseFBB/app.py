from flask import Flask, jsonify, request, render_template
from db_manager import DBManager
import db_importer
import os

app = Flask(__name__, template_folder="templates", static_folder="static")

# Render Frontend
@app.route("/")
def index():
    return render_template("index.html")

# 1. Dashboard API
@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    try:
        branch = request.args.get("branch", "").strip()
        zone = request.args.get("zone", "").strip()
        stats = DBManager.get_dashboard_stats(branch=branch, zone=zone)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Filter Options API
@app.route("/api/filters", methods=["GET"])
def get_filters():
    try:
        filters = DBManager.get_filter_options()
        return jsonify(filters)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/branches/<branch>/zones", methods=["GET"])
def get_branch_zones(branch):
    try:
        conn = DBManager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT zone FROM zones WHERE branch = ? AND zone IS NOT NULL AND zone != '' ORDER BY zone", (branch,))
        zones = [r["zone"] for r in cursor.fetchall()]
        conn.close()
        return jsonify(zones)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. ZONES REST API
@app.route("/api/zones", methods=["GET"])
def get_zones():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 15))
        search = request.args.get("search", "").strip()
        branch = request.args.get("branch", "").strip()
        department = request.args.get("department", "").strip()
        sort_by = request.args.get("sort_by", "zone").strip()
        sort_dir = request.args.get("sort_dir", "ASC").strip()
        
        result = DBManager.get_zones(
            page=page,
            per_page=per_page,
            search=search,
            branch=branch,
            department=department,
            sort_by=sort_by,
            sort_dir=sort_dir
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/zones/<int:zone_id>", methods=["GET"])
def get_zone_detail(zone_id):
    try:
        zone = DBManager.get_zone(zone_id)
        if zone:
            return jsonify(zone)
        return jsonify({"error": "Zona no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/zones", methods=["POST"])
def create_zone():
    try:
        data = request.json
        if not data or not data.get("zone"):
            return jsonify({"error": "El campo 'zone' (nombre de la zona) es obligatorio"}), 400
        
        new_id = DBManager.add_zone(data)
        return jsonify({"message": "Zona creada exitosamente", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/zones/<int:zone_id>", methods=["PUT"])
def update_zone(zone_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
            
        success = DBManager.update_zone(zone_id, data)
        if success:
            return jsonify({"message": "Zona actualizada exitosamente"})
        return jsonify({"error": "Zona no encontrada o no se realizaron cambios"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/zones/<int:zone_id>", methods=["DELETE"])
def delete_zone(zone_id):
    try:
        success = DBManager.delete_zone(zone_id)
        if success:
            return jsonify({"message": "Zona eliminada exitosamente"})
        return jsonify({"error": "Zona no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. BOXES REST API
@app.route("/api/boxes", methods=["GET"])
def get_boxes():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 15))
        search = request.args.get("search", "").strip()
        zone = request.args.get("zone", "").strip()
        olt = request.args.get("olt", "").strip()
        branch = request.args.get("branch", "").strip()
        box_class = request.args.get("box_class", "").strip()
        site_logical = request.args.get("site_logical", "").strip()
        sort_by = request.args.get("sort_by", "node_code").strip()
        sort_dir = request.args.get("sort_dir", "ASC").strip()
        
        result = DBManager.get_boxes(
            page=page,
            per_page=per_page,
            search=search,
            zone=zone,
            olt=olt,
            branch=branch,
            box_class=box_class,
            site_logical=site_logical,
            sort_by=sort_by,
            sort_dir=sort_dir
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/boxes/<int:box_id>", methods=["GET"])
def get_box_detail(box_id):
    try:
        box = DBManager.get_box(box_id)
        if box:
            return jsonify(box)
        return jsonify({"error": "Caja no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/boxes", methods=["POST"])
def create_box():
    try:
        data = request.json
        if not data or not data.get("node_code"):
            return jsonify({"error": "El campo 'node_code' (código de nodo) es obligatorio"}), 400
            
        new_id = DBManager.add_box(data)
        return jsonify({"message": "Caja creada exitosamente", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/boxes/<int:box_id>", methods=["PUT"])
def update_box(box_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
            
        success = DBManager.update_box(box_id, data)
        if success:
            return jsonify({"message": "Caja actualizada exitosamente"})
        return jsonify({"error": "Caja no encontrada o no se realizaron cambios"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/boxes/<int:box_id>", methods=["DELETE"])
def delete_box(box_id):
    try:
        success = DBManager.delete_box(box_id)
        if success:
            return jsonify({"message": "Caja eliminada exitosamente"})
        return jsonify({"error": "Caja no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# 4.5 NEAREST BOXES API
@app.route("/api/boxes/nearest", methods=["GET"])
def get_nearest_boxes():
    try:
        lat = float(request.args.get("latitude"))
        lng = float(request.args.get("longitude"))
        limit = int(request.args.get("limit", 12))
        
        result = DBManager.get_nearest_boxes(lat, lng, limit)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 5. STAFF REST API
@app.route("/api/staff", methods=["GET"])
def get_staff():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 15))
        search = request.args.get("search", "").strip()
        branch = request.args.get("branch", "").strip()
        partner = request.args.get("partner", "").strip()
        sort_by = request.args.get("sort_by", "staff_team").strip()
        sort_dir = request.args.get("sort_dir", "ASC").strip()
        
        result = DBManager.get_staff(
            page=page,
            per_page=per_page,
            search=search,
            branch=branch,
            partner=partner,
            sort_by=sort_by,
            sort_dir=sort_dir
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff/<int:staff_id>", methods=["GET"])
def get_staff_detail(staff_id):
    try:
        member = DBManager.get_staff_member(staff_id)
        if member:
            return jsonify(member)
        return jsonify({"error": "Miembro del personal no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff", methods=["POST"])
def create_staff():
    try:
        data = request.json
        if not data or not data.get("staff_team") or not data.get("zone"):
            return jsonify({"error": "Los campos 'staff_team' y 'zone' son obligatorios"}), 400
            
        new_id = DBManager.add_staff(data)
        return jsonify({"message": "Miembro del personal creado exitosamente", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff/<int:staff_id>", methods=["PUT"])
def update_staff(staff_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
            
        success = DBManager.update_staff(staff_id, data)
        if success:
            return jsonify({"message": "Información del personal actualizada exitosamente"})
        return jsonify({"error": "Personal no encontrado o no se realizaron cambios"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff/<int:staff_id>", methods=["DELETE"])
def delete_staff(staff_id):
    try:
        success = DBManager.delete_staff(staff_id)
        if success:
            return jsonify({"message": "Registro de personal eliminado exitosamente"})
        return jsonify({"error": "Personal no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 6. SYNC API
@app.route("/api/sync", methods=["POST"])
def sync_with_google_sheet():
    try:
        zones_count, boxes_count, staff_count, incidents_count, deployments_count = db_importer.sync_data()
        return jsonify({
            "message": "Sincronización exitosa desde Google Sheets",
            "zones_imported": zones_count,
            "boxes_imported": boxes_count,
            "staff_imported": staff_count,
            "incidents_imported": incidents_count,
            "deployments_imported": deployments_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 7. STAFF IMPORT/EXPORT API
@app.route("/api/staff/export", methods=["GET"])
def export_staff():
    try:
        csv_data = DBManager.export_staff_csv()
        csv_bytes = csv_data.encode("utf-8-sig")
        from flask import Response
        return Response(
            csv_bytes,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=plantilla_staff.csv"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff/import", methods=["POST"])
def import_staff():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No se subió ningún archivo."}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Nombre de archivo vacío."}), 400
            
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "El archivo debe ser un formato CSV."}), 400
            
        csv_content = file.read()
        created, updated, errors = DBManager.import_staff_csv(csv_content)
        
        return jsonify({
            "message": "Importación procesada.",
            "created": created,
            "updated": updated,
            "errors": errors
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 8. PARTNER CAPACITY REPORTING API
@app.route("/api/partners/capacity", methods=["GET"])
def get_partners_capacity_report():
    try:
        report = DBManager.get_partner_capacity_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/zones/capacity-detail", methods=["GET"])
def get_zones_capacity_detail_report():
    try:
        detail = DBManager.get_zone_capacity_detail()
        return jsonify(detail)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 9. STACKED CAPACITY CHART API
@app.route("/api/charts/branch-capacity-stacked", methods=["GET"])
def get_branch_capacity_stacked():
    try:
        branch = request.args.get("branch", "").strip()
        partner = request.args.get("partner", "").strip()
        zone = request.args.get("zone", "").strip()
        report = DBManager.get_branch_capacity_stacked_report(branch=branch, partner=partner, zone=zone)
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 10. INCIDENTS API
@app.route("/api/incidents/stats", methods=["GET"])
def get_incidents_stats():
    try:
        site = request.args.get("site", "").strip()
        branch = request.args.get("branch", "").strip()
        month = request.args.get("month", "").strip()
        week = request.args.get("week", "").strip()
        
        evolution = DBManager.get_incidents_by_month(branch=branch, month=month, site=site, week=week)
        status = DBManager.get_incidents_by_status(branch=branch, month=month, site=site, week=week)
        ranking = DBManager.get_incidents_sites_ranking(branch=branch, month=month, site=site, week=week)
        monthly_breakdown = DBManager.get_incidents_monthly_breakdown(branch=branch, month=month, site=site, week=week)
        site_breakdown = DBManager.get_incidents_site_breakdown(branch=branch, month=month, site=site, week=week)
        
        # Calculate summary metrics
        conn = DBManager.get_connection()
        cursor = conn.cursor()
        
        query_parts = ["WHERE 1=1"]
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
            
        where_clause = " AND ".join(query_parts)
        
        cursor.execute(f"SELECT COUNT(*), COUNT(DISTINCT subscriber) FROM incidents {where_clause}", params)
        counts = cursor.fetchone()
        tot_inc = counts[0] or 0
        uniq_cli = counts[1] or 0
        conn.close()
        
        most_freq_status = status[0]["status_desc"] if status else "N/A"
        most_freq_count = status[0]["count"] if status else 0
        
        return jsonify({
            "evolution": evolution,
            "status": status,
            "ranking": ranking,
            "monthly_breakdown": monthly_breakdown,
            "site_breakdown": site_breakdown,
            "kpis": {
                "total_incidents": tot_inc,
                "unique_clients": uniq_cli,
                "most_frequent_status": most_freq_status,
                "most_frequent_count": most_freq_count
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/incidents/sites", methods=["GET"])
def get_incidents_sites():
    try:
        branch = request.args.get("branch", "").strip()
        sites = DBManager.get_incidents_sites(branch=branch)
        return jsonify(sites)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/incidents/months", methods=["GET"])
def get_incidents_months():
    try:
        months = DBManager.get_incidents_months()
        return jsonify(months)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/deployments/months", methods=["GET"])
def get_deployments_months():
    try:
        months = DBManager.get_deployments_months()
        return jsonify(months)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/incidents/outages", methods=["GET"])
def get_site_outages():
    try:
        branch = request.args.get("branch", "").strip()
        month = request.args.get("month", "").strip()
        site = request.args.get("site", "").strip()
        week = request.args.get("week", "").strip()
        
        outages_ranking = DBManager.get_site_outages_report(branch=branch, month=month, site=site, week=week)
        causes = DBManager.get_site_outage_causes(branch=branch, month=month, site=site, week=week)
        
        # Calculate KPIs
        total_energy_cuts = sum(r.get("energy_cuts", 0) for r in outages_ranking)
        total_energy_affected = sum(r.get("energy_affected", 0) for r in outages_ranking)
        total_odn_cuts = sum(r.get("odn_cuts", 0) for r in outages_ranking)
        total_odn_affected = sum(r.get("odn_affected", 0) for r in outages_ranking)
        total_wos = sum(r.get("total_wos", 0) for r in outages_ranking)
        
        return jsonify({
            "outages_ranking": outages_ranking,
            "causes": causes,
            "kpis": {
                "total_energy_cuts": total_energy_cuts,
                "total_energy_affected": total_energy_affected,
                "total_odn_cuts": total_odn_cuts,
                "total_odn_affected": total_odn_affected,
                "total_wos": total_wos
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/incidents/outages/details", methods=["GET"])
def get_site_outage_details():
    try:
        site = request.args.get("site", "").strip()
        branch = request.args.get("branch", "").strip()
        month = request.args.get("month", "").strip()
        week = request.args.get("week", "").strip()
        
        if not site:
            return jsonify({"error": "site parameter is required"}), 400
            
        details = DBManager.get_site_outage_details(site=site, branch=branch, month=month, week=week)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/incidents/wos/details", methods=["GET"])
def get_site_wo_details():
    try:
        site = request.args.get("site", "").strip()
        branch = request.args.get("branch", "").strip()
        month = request.args.get("month", "").strip()
        week = request.args.get("week", "").strip()
        
        if not site:
            return jsonify({"error": "site parameter is required"}), 400
            
        details = DBManager.get_site_wo_details(site=site, branch=branch, month=month, week=week)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/incidents/weeks", methods=["GET"])
def get_incidents_weeks():
    try:
        weeks = DBManager.get_incidents_weeks()
        return jsonify(weeks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 11. DEPLOYMENTS STATS API
@app.route("/api/deployments/stats", methods=["GET"])
def get_deployments_stats():
    try:
        branch = request.args.get("branch", "").strip()
        month = request.args.get("month", "").strip()
        stats = DBManager.get_deployments_report(branch=branch, month=month)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
