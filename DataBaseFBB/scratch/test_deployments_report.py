import sqlite3

def get_deployments_report(branch="", month=""):
    conn = sqlite3.connect("fbb_database.db")
    conn.row_factory = sqlite3.Row
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
        
    query = f"""
        SELECT 
            partner,
            branch,
            COUNT(*) as total_tasks,
            SUM(CASE WHEN kpi_from_paid = '<24H' THEN 1 ELSE 0 END) as tasks_24h,
            SUM(CASE WHEN kpi_from_paid IN ('<24H', '<48H') THEN 1 ELSE 0 END) as tasks_48h,
            SUM(CASE WHEN kpi_from_paid IN ('<24H', '<48H', '<72H') THEN 1 ELSE 0 END) as tasks_72h
        FROM deployments
        {where_clause}
        GROUP BY partner, branch
    """
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    cursor.execute("SELECT branch, partner, teams_deploy, ft_total FROM partner_capacities")
    capacities = {}
    for r in cursor.fetchall():
        br = r["branch"] or ""
        p = r["partner"] or ""
        key = (br.upper().strip(), p.upper().strip())
        capacities[key] = {
            "teams_deploy": r["teams_deploy"] or 0,
            "ft_total": r["ft_total"] or 0
        }
        
    cursor.execute("SELECT branch, partner, COUNT(DISTINCT zone) as zones_count FROM zone_assignments GROUP BY branch, partner")
    zones_assigned = {}
    for r in cursor.fetchall():
        br = r["branch"] or ""
        p = r["partner"] or ""
        key = (br.upper().strip(), p.upper().strip())
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
        
        tasks = r["total_tasks"] or 0
        t24 = r["tasks_24h"] or 0
        t48 = r["tasks_48h"] or 0
        t72 = r["tasks_72h"] or 0
        
        sla_24 = round((t24 * 100.0) / tasks, 2) if tasks > 0 else 0.0
        sla_48 = round((t48 * 100.0) / tasks, 2) if tasks > 0 else 0.0
        sla_72 = round((t72 * 100.0) / tasks, 2) if tasks > 0 else 0.0
        
        teams = cap["teams_deploy"] or 0
        ft = cap["ft_total"] or 0
        
        tasks_per_team = round(tasks / teams, 1) if teams > 0 else None
        zones_per_team = round(zones_count / teams, 1) if teams > 0 else None
        techs_per_zone = round(ft / zones_count, 1) if zones_count > 0 else None
        
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
            "techs_per_zone": techs_per_zone
        })
        
    # Group by Partner
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
                "assigned_zones": 0
            }
        partner_agg[p]["total_tasks"] += row["total_tasks"]
        partner_agg[p]["tasks_24h"] += row["tasks_24h"]
        partner_agg[p]["tasks_48h"] += row["tasks_48h"]
        partner_agg[p]["tasks_72h"] += row["tasks_72h"]
        partner_agg[p]["teams_deploy"] += row["teams_deploy"]
        partner_agg[p]["ft_total"] += row["ft_total"]
        partner_agg[p]["assigned_zones"] += row["assigned_zones"]
        
    partner_stats = []
    for p, agg in partner_agg.items():
        tasks = agg["total_tasks"]
        teams = agg["teams_deploy"]
        zones = agg["assigned_zones"]
        ft = agg["ft_total"]
        
        agg["sla_24h_pct"] = round((agg["tasks_24h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
        agg["sla_48h_pct"] = round((agg["tasks_48h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
        agg["sla_72h_pct"] = round((agg["tasks_72h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
        agg["tasks_per_team"] = round(tasks / teams, 1) if teams > 0 else None
        agg["zones_per_team"] = round(zones / teams, 1) if teams > 0 else None
        agg["techs_per_zone"] = round(ft / zones, 1) if zones > 0 else None
        partner_stats.append(agg)
        
    # Group by Branch
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
                "assigned_zones": 0
            }
        branch_agg[br]["total_tasks"] += row["total_tasks"]
        branch_agg[br]["tasks_24h"] += row["tasks_24h"]
        branch_agg[br]["tasks_48h"] += row["tasks_48h"]
        branch_agg[br]["tasks_72h"] += row["tasks_72h"]
        branch_agg[br]["teams_deploy"] += row["teams_deploy"]
        branch_agg[br]["ft_total"] += row["ft_total"]
        branch_agg[br]["assigned_zones"] += row["assigned_zones"]
        
    branch_stats = []
    for br, agg in branch_agg.items():
        tasks = agg["total_tasks"]
        teams = agg["teams_deploy"]
        zones = agg["assigned_zones"]
        ft = agg["ft_total"]
        
        agg["sla_24h_pct"] = round((agg["tasks_24h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
        agg["sla_48h_pct"] = round((agg["tasks_48h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
        agg["sla_72h_pct"] = round((agg["tasks_72h"] * 100.0) / tasks, 2) if tasks > 0 else 0.0
        agg["tasks_per_team"] = round(tasks / teams, 1) if teams > 0 else None
        agg["zones_per_team"] = round(zones / teams, 1) if teams > 0 else None
        agg["techs_per_zone"] = round(ft / zones, 1) if zones > 0 else None
        branch_stats.append(agg)
        
    # Overall
    total_tasks = sum(r["total_tasks"] for r in detail_table)
    total_24h = sum(r["tasks_24h"] for r in detail_table)
    total_48h = sum(r["tasks_48h"] for r in detail_table)
    total_72h = sum(r["tasks_72h"] for r in detail_table)
    
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
        "techs_per_zone": round(overall_techs / overall_zones, 1) if overall_zones > 0 else None
    }
    
    conn.close()
    return {
        "overall": overall,
        "partner_stats": partner_stats,
        "branch_stats": branch_stats,
        "detail_table": detail_table
    }

res = get_deployments_report()
print("Overall:")
print(res["overall"])
print("\nSample partner stat:")
if res["partner_stats"]:
    print(res["partner_stats"][0])
print("\nSample detail row:")
if res["detail_table"]:
    print(res["detail_table"][0])
