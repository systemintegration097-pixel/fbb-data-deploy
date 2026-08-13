"""
build_and_push_coverage.py — parte la cobertura KML global (DataBaseFBB/static/
coverage.geojson) en un subconjunto por sucursal, usando el mapeo site_code ->
branch que ya vive en gnoc.db (tabla kpi_zonas_map), y sube cada subconjunto a
la app en la nube para que cada encargado vea SOLO la cobertura de su sucursal.

Se corre a mano (no está enganchado al sync automático de despliegues) porque
la cobertura KML casi no cambia. Volver a correrlo cuando se actualice el KML.

Uso:
    python build_and_push_coverage.py
"""
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import cloud_sync

BASE_DIR = Path(__file__).resolve().parent
COVERAGE_PATH = BASE_DIR / "DataBaseFBB" / "static" / "coverage.geojson"
GNOC_DB_PATH = BASE_DIR / "gnoc.db"

SITE_CODE_RE = re.compile(r"([A-Z]{3}\d{4})OLT")


def _load_site_to_branch():
    conn = sqlite3.connect(GNOC_DB_PATH)
    try:
        return dict(conn.execute("SELECT site_code, branch FROM kpi_zonas_map"))
    finally:
        conn.close()


def main():
    if not cloud_sync.is_configured():
        print("CLOUD_SYNC_URL/CLOUD_API_KEY no configurados en .env -- nada que subir.")
        return

    with open(COVERAGE_PATH, encoding="utf-8") as f:
        coverage = json.load(f)

    site_to_branch = _load_site_to_branch()

    by_branch = defaultdict(list)
    unmatched = 0
    for feature in coverage.get("features", []):
        name = (feature.get("properties") or {}).get("name", "")
        m = SITE_CODE_RE.search(name)
        branch = site_to_branch.get(m.group(1)) if m else None
        if not branch:
            unmatched += 1
            continue
        by_branch[branch].append(feature)

    print(f"Total features: {len(coverage.get('features', []))} | sin branch identificado: {unmatched}")

    for branch, features in sorted(by_branch.items()):
        geojson_obj = {"type": "FeatureCollection", "features": features}
        result = cloud_sync.push_coverage(branch, geojson_obj)
        print(f"{branch}: {len(features)} polígonos -> {result}")


if __name__ == "__main__":
    main()
