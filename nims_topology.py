import re
import sqlite3
import json

def parse_box_code(raw_code):
    """
    Parsea un código de caja o conector (ej: ANC0001_XB01_HB01_SB111, XB01_HB01_SB111_01, SB231, EX114)
    y retorna la estructura completa de topología.
    """
    if not raw_code:
        return None

    raw_code = str(raw_code).strip()
    
    site_code = None
    xb_code = None
    hb_code = None
    line_code = None
    box_code = None
    expansion_code = None

    # 1. Intentar extraer Site Code (ej: ARE0001, ANC0001, LI10005)
    site_match = re.search(r'([A-Z]{2,4}\d{4,5})', raw_code)
    if site_match:
        site_code = site_match.group(1)

    # 2. Extraer XB (XB01, XB02)
    xb_match = re.search(r'(XB0[12])', raw_code, re.IGNORECASE)
    if xb_match:
        xb_code = xb_match.group(1).upper()

    # 3. Extraer HB (HB01, HB02, HB03, HB04)
    hb_match = re.search(r'(HB0[1-4])', raw_code, re.IGNORECASE)
    if hb_match:
        hb_code = hb_match.group(1).upper()

    # 4. Extraer Caja SB / EB / EX (ej: SB111, EB114, EX231, _SB111)
    box_match = re.search(r'(SB|EB|EX)(\d{3})', raw_code, re.IGNORECASE)
    if box_match:
        prefix = box_match.group(1).upper()
        digits = box_match.group(2)
        
        hb_num = int(digits[0])
        line_num = int(digits[1])
        pos_num = int(digits[2])
        
        if not hb_code and 1 <= hb_num <= 4:
            hb_code = f"HB0{hb_num}"
            
        if 1 <= line_num <= 4:
            line_code = f"Línea {line_num}"

        if prefix == 'EX':
            expansion_code = f"EX{digits}"
            main_prefix = 'EB' if pos_num == 4 else 'SB'
            box_code = f"{main_prefix}{digits}"
        else:
            box_code = f"{prefix}{digits}"
            expansion_code = f"EX{digits}"
            
    # Asignar XB1 por defecto si no hay XB pero hay HB
    if hb_code and not xb_code:
        xb_code = "XB01"

    # Construir la ruta jerárquica
    route = []
    if site_code:
        route.append(site_code)
    if xb_code:
        route.append(xb_code)
    if hb_code:
        route.append(hb_code)
    if line_code:
        route.append(line_code)
    if box_code:
        route.append(box_code)
    if expansion_code and raw_code.upper().startswith("EX"):
        route.append(expansion_code)

    parent = route[-2] if len(route) >= 2 else None

    return {
        "site_code": site_code,
        "xb_code": xb_code,
        "hb_code": hb_code,
        "line_code": line_code,
        "box_code": box_code,
        "expansion_code": expansion_code,
        "parent": parent,
        "full_route": " -> ".join(route) if route else raw_code,
        "route_list": route
    }

def get_boxes_for_line(hb_num, line_num):
    """
    Retorna la lista de cajas de una línea: 3 SB y 1 EB.
    """
    boxes = []
    for pos in range(1, 4):
        boxes.append(f"SB{hb_num}{line_num}{pos}")
    boxes.append(f"EB{hb_num}{line_num}4")
    return boxes

def generate_site_topology(site_code):
    """
    Genera la estructura teórica completa de topología de red para un Site.
    """
    site_tree = {
        "site_code": site_code,
        "xbs": []
    }
    
    for xb_idx in [1, 2]:
        xb_node = {
            "xb_code": f"XB0{xb_idx}",
            "hbs": []
        }
        for hb_idx in range(1, 5):
            hb_node = {
                "hb_code": f"HB0{hb_idx}",
                "lines": []
            }
            for line_idx in range(1, 5):
                line_node = {
                    "line_code": f"Línea {line_idx}",
                    "boxes": []
                }
                boxes = get_boxes_for_line(hb_idx, line_idx)
                for b in boxes:
                    digits = b[2:]
                    line_node["boxes"].append({
                        "box_code": b,
                        "expansion_code": f"EX{digits}"
                    })
                hb_node["lines"].append(line_node)
            xb_node["hbs"].append(hb_node)
        site_tree["xbs"].append(xb_node)
        
    return site_tree

def analyze_faults_by_topology(db_path="gnoc.db"):
    """
    Analiza y agrupa todas las órdenes de trabajo por Caja, Línea, HB, XB y Sitio.
    Retorna un reporte estructurado para la interfaz web.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Obtener todas las WOs con información topológica
    cursor.execute("""
        SELECT 
            wo_code, account, wo_status, create_time, wo_create_date,
            close_reason, description, is_error, connector_code,
            site_code, xb_code, hb_code, line_code, box_code, expansion_code
        FROM work_orders
    """)
    rows = cursor.fetchall()
    conn.close()

    site_summary = {}
    box_summary = {}
    line_summary = {}

    for row in rows:
        wo_code = row["wo_code"]
        account = row["account"] or "N/A"
        raw_conn = row["connector_code"] or ""
        
        # Usar los campos pre-calculados de work_orders, con fallback a parse_box_code si están vacíos
        site = row["site_code"]
        xb = order_xb = row["xb_code"]
        hb = order_hb = row["hb_code"]
        line = order_line = row["line_code"]
        box = order_box = row["box_code"]
        ex = row["expansion_code"]
        
        if not site or site == "SITIO DESCONOCIDO" or not box:
            parsed = parse_box_code(raw_conn) if raw_conn else None
            if not site: site = (parsed["site_code"] if parsed else "SITIO DESCONOCIDO") or "SITIO DESCONOCIDO"
            if not xb: xb = (parsed["xb_code"] if parsed else "XB DESCONOCIDO") or "XB DESCONOCIDO"
            if not hb: hb = (parsed["hb_code"] if parsed else "HB DESCONOCIDO") or "HB DESCONOCIDO"
            if not line: line = (parsed["line_code"] if parsed else "LÍNEA DESCONOCIDA") or "LÍNEA DESCONOCIDA"
            if not box: box = (parsed["box_code"] if parsed else "CAJA DESCONOCIDA") or "CAJA DESCONOCIDA"
            if not ex: ex = (parsed["expansion_code"] if parsed else "") or ""
            
        is_err = row["is_error"] or 0
        create_date = (row["wo_create_date"] or row["create_time"] or "")[:10]
        reason = row["close_reason"] or "En Proceso"

        # Agrupar por Sitio
        if site not in site_summary:
            site_summary[site] = {
                "site_code": site,
                "total_wos": 0,
                "total_errors": 0,
                "accounts": set(),
                "boxes_affected": set(),
                "dates": set(),
                "reasons": {}
            }
        site_summary[site]["total_wos"] += 1
        if is_err:
            site_summary[site]["total_errors"] += 1
        site_summary[site]["accounts"].add(account)
        site_summary[site]["boxes_affected"].add(box)
        if create_date:
            site_summary[site]["dates"].add(create_date)
        site_summary[site]["reasons"][reason] = site_summary[site]["reasons"].get(reason, 0) + 1

        # Agrupar por Caja
        box_key = f"{site} -> {box}"
        if box_key not in box_summary:
            box_summary[box_key] = {
                "site_code": site,
                "box_code": box,
                "expansion_code": ex,
                "xb_code": xb,
                "hb_code": hb,
                "line_code": line,
                "full_route": f"{site} -> {xb} -> {hb} -> {line} -> {box}",
                "total_wos": 0,
                "total_errors": 0,
                "accounts": set(),
                "wos": [],
                "dates": set(),
                "reasons": {}
            }
        box_summary[box_key]["total_wos"] += 1
        if is_err:
            box_summary[box_key]["total_errors"] += 1
        box_summary[box_key]["accounts"].add(account)
        box_summary[box_key]["wos"].append(wo_code)
        if create_date:
            box_summary[box_key]["dates"].add(create_date)
        box_summary[box_key]["reasons"][reason] = box_summary[box_key]["reasons"].get(reason, 0) + 1

    # Formatear conjuntos para JSON
    formatted_sites = []
    for s_code, s_data in sorted(site_summary.items(), key=lambda x: x[1]["total_wos"], reverse=True):
        formatted_sites.append({
            "site_code": s_code,
            "total_wos": s_data["total_wos"],
            "total_errors": s_data["total_errors"],
            "affected_accounts": len(s_data["accounts"]),
            "boxes_count": len(s_data["boxes_affected"]),
            "dates": sorted(list(s_data["dates"])),
            "top_reasons": sorted(s_data["reasons"].items(), key=lambda x: x[1], reverse=True)[:5]
        })

    formatted_boxes = []
    for b_key, b_data in sorted(box_summary.items(), key=lambda x: x[1]["total_wos"], reverse=True):
        formatted_boxes.append({
            "site_code": b_data["site_code"],
            "box_code": b_data["box_code"],
            "expansion_code": b_data["expansion_code"],
            "full_route": b_data["full_route"],
            "line_code": b_data["line_code"],
            "hb_code": b_data["hb_code"],
            "xb_code": b_data["xb_code"],
            "total_wos": b_data["total_wos"],
            "total_errors": b_data["total_errors"],
            "affected_accounts": len(b_data["accounts"]),
            "wos": b_data["wos"],
            "dates": sorted(list(b_data["dates"])),
            "top_reasons": sorted(b_data["reasons"].items(), key=lambda x: x[1], reverse=True)[:5]
        })

    return {
        "summary": {
            "total_sites_affected": len(formatted_sites),
            "total_boxes_affected": len(formatted_boxes),
            "total_wos_analyzed": len(rows)
        },
        "sites": formatted_sites,
        "boxes": formatted_boxes
    }

if __name__ == "__main__":
    test_code = "ANC0001_XB01_HB01_SB111"
    print("Prueba de parseo topológico:")
    print(json.dumps(parse_box_code(test_code), indent=2))
