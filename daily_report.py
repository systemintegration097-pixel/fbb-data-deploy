"""
daily_report.py — "Reporte Diario":
  - Instalaciones (deployments) por día/semana por branch, desde DataBaseFBB
    (tabla deployments, columna finish_date -- List_Deployed.csv).
  - Averías pendientes por branch (desde julio en adelante) y cuántas se están
    cerrando por mes/semana/día, "de acuerdo a GNOC" (work_orders en gnoc.db).

Reutiliza kpi_calc.get_enriched_wos() para el lado GNOC (mismas fechas ya limpias
y el mismo mapeo de branch que usa el Reporte KPI) en vez de leer la tabla
'incidents' de DataBaseFBB, que es el mismo dato pero importado por separado con
fechas sin normalizar -ver investigación previa: incidents y work_orders son el
mismo WO, work_orders es la fuente limpia y ya tiene el estado "Pending" resuelto.
"""
import os
import sqlite3
from datetime import datetime, timedelta

import kpi_calc

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
FBB_DB_PATH = os.path.join(BASE_PATH, "DataBaseFBB", "fbb_database.db")

PENDING_SINCE_MONTH = "2026-07"  # "averías pendientes por branch desde julio en adelante"


def _fbb_conn():
    conn = sqlite3.connect(FBB_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────────────────────
#  Instalaciones (deployments)
# ─────────────────────────────────────────────────────────────────────────────

def _load_deployments_df():
    import pandas as pd
    conn = _fbb_conn()
    df = pd.read_sql_query("""
        SELECT branch, partner, finish_date FROM deployments
        WHERE finish_date IS NOT NULL AND finish_date != ''
    """, conn)
    conn.close()
    df["finish_date"] = pd.to_datetime(df["finish_date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["finish_date"])
    df["branch"] = df["branch"].fillna("").str.strip()
    df["partner"] = df["partner"].fillna("").str.strip()
    df["day_key"] = df["finish_date"].dt.strftime("%Y-%m-%d")
    df["month_key"] = df["finish_date"].dt.strftime("%Y-%m")
    # Misma convención lunes-domingo que kpi_calc, para que ambos reportes hablen
    # de "la misma semana" cuando se muestran juntos.
    week_monday = df["finish_date"] - pd.to_timedelta(df["finish_date"].dt.weekday, unit="D")
    df["week_key"] = week_monday.dt.strftime("%Y-%m-%d")
    return df


def compute_installs_by_partner(days_back=90):
    """Instalaciones día a día por partner de los últimos `days_back` días (se manda ya
    con suficiente historia para que el portal en la nube pueda filtrar cualquier rango
    hasta ese tope sin pedir de nuevo al dashboard local -mismo criterio que
    installs_by_month/installs_by_week, ver build_cloud_payload)."""
    df = _load_deployments_df()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    df_period = df[df["day_key"] >= cutoff]
    partners = sorted(p for p in df_period["partner"].unique().tolist() if p)
    by_day = []
    for day in sorted(df_period["day_key"].unique().tolist()):
        sub = df_period[df_period["day_key"] == day]
        row = {"day": day, "total": int(len(sub))}
        for p in partners:
            row[p] = int((sub["partner"] == p).sum())
        by_day.append(row)
    return {"partners": partners, "days": by_day}


def compute_installs_daily(month_key):
    """month_key: 'YYYY-MM'. Instalaciones por día y branch dentro de ese mes."""
    df = _load_deployments_df()
    df_period = df[df["month_key"] == month_key]
    days = sorted(df_period["day_key"].unique().tolist())
    by_day = []
    for day in days:
        sub = df_period[df_period["day_key"] == day]
        row = {"day": day, "total": int(len(sub))}
        for br in kpi_calc.BRANCHES:
            row[br] = int((sub["branch"] == br).sum())
        by_day.append(row)
    return by_day


def compute_installs_weekly(week_key):
    """week_key: 'YYYY-MM-DD' (lunes). Instalaciones por branch en esa semana."""
    df = _load_deployments_df()
    df_period = df[df["week_key"] == week_key]
    branch_table = [{"branch": br, "qty": int((df_period["branch"] == br).sum())} for br in kpi_calc.BRANCHES]
    return {"branch_table": branch_table, "total": int(len(df_period))}


def get_installs_available_periods():
    df = _load_deployments_df()
    months = sorted(df["month_key"].dropna().unique().tolist())
    weeks = sorted(df["week_key"].dropna().unique().tolist())
    month_options = [
        {"month_key": m, "label": f"{kpi_calc.MONTH_NAMES_ES[int(m[5:7]) - 1]} {m[:4]}"}
        for m in months
    ]
    week_options = []
    for w in weeks:
        monday = datetime.strptime(w, "%Y-%m-%d")
        sunday = monday + timedelta(days=6)
        week_options.append({"week_key": w, "label": f"{monday.strftime('%d/%m')}-{sunday.strftime('%d/%m')}"})
    return {"months": month_options, "weeks": week_options}


# ─────────────────────────────────────────────────────────────────────────────
#  Averías pendientes / cerradas, según GNOC (work_orders)
# ─────────────────────────────────────────────────────────────────────────────

def compute_pending_by_branch(since_month=PENDING_SINCE_MONTH):
    """branch_table trae, por branch, el mismo desglose de horas pendientes que usa el
    dashboard local (/api/reports/branch_sla en server.py): under_24h (0-24h), under_48h
    (24-48h), under_72h (48-72h), over_72h (>72h) -"hours" ya viene calculada por
    kpi_calc (tiempo transcurrido desde create_time para las que siguen Pending)."""
    wos = kpi_calc.get_enriched_wos()
    df = wos[(wos["month_key"] >= since_month) & (wos["kpi_closing"] == "Pending")]
    branch_table = []
    for br in kpi_calc.BRANCHES:
        sub = df[df["branch"] == br]
        hours = sub["hours"]
        branch_table.append({
            "branch": br,
            "qty_pending": int(len(sub)),
            "under_24h": int(((hours > 0) & (hours <= 24)).sum()),
            "under_48h": int(((hours > 24) & (hours <= 48)).sum()),
            "under_72h": int(((hours > 48) & (hours <= 72)).sum()),
            "over_72h": int((hours > 72).sum()),
        })
    return {"branch_table": branch_table, "total_pending": int(len(df)), "since_month": since_month}


def compute_closures_by_month(since_month=PENDING_SINCE_MONTH):
    wos = kpi_calc.get_enriched_wos()
    closed = wos[wos["closed_time"].notna()].copy()
    closed["closed_month_key"] = closed["closed_time"].dt.strftime("%Y-%m")
    closed = closed[closed["closed_month_key"] >= since_month]
    counts = closed.groupby("closed_month_key").size()
    return [
        {"month_key": m, "month_name": kpi_calc.MONTH_NAMES_ES[int(m[5:7]) - 1], "qty_closed": int(counts[m])}
        for m in sorted(counts.index.tolist())
    ]


def compute_closures_by_week(since_month=PENDING_SINCE_MONTH):
    import pandas as pd
    wos = kpi_calc.get_enriched_wos()
    closed = wos[wos["closed_time"].notna()].copy()
    week_monday = closed["closed_time"] - pd.to_timedelta(closed["closed_time"].dt.weekday, unit="D")
    closed["closed_week_key"] = week_monday.dt.strftime("%Y-%m-%d")
    closed = closed[closed["closed_week_key"] >= f"{since_month}-01"]
    counts = closed.groupby("closed_week_key").size()
    result = []
    for w in sorted(counts.index.tolist()):
        monday = datetime.strptime(w, "%Y-%m-%d")
        sunday = monday + timedelta(days=6)
        result.append({"week_key": w, "week_label": f"{monday.strftime('%d/%m')}-{sunday.strftime('%d/%m')}", "qty_closed": int(counts[w])})
    return result


def compute_closures_by_day(since_month=PENDING_SINCE_MONTH):
    wos = kpi_calc.get_enriched_wos()
    closed = wos[wos["closed_time"].notna()].copy()
    closed["closed_day_key"] = closed["closed_time"].dt.strftime("%Y-%m-%d")
    closed = closed[closed["closed_day_key"] >= f"{since_month}-01"]
    counts = closed.groupby("closed_day_key").size()
    return [{"day": d, "qty_closed": int(counts[d])} for d in sorted(counts.index.tolist())]


# ─────────────────────────────────────────────────────────────────────────────
#  Snapshot autocontenido para el portal admin en la nube (cloud_app) -- incluye
#  instalaciones de TODOS los meses/semanas disponibles para que el toggle
#  Mensual/Semanal funcione allá sin más round-trips al servidor local.
# ─────────────────────────────────────────────────────────────────────────────

def build_cloud_payload():
    periods = get_installs_available_periods()
    installs_by_month = {m["month_key"]: compute_installs_daily(m["month_key"]) for m in periods["months"]}
    installs_by_week = {w["week_key"]: compute_installs_weekly(w["week_key"]) for w in periods["weeks"]}
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overview": {
            "pending": compute_pending_by_branch(),
            "closures_by_month": compute_closures_by_month(),
            "closures_by_week": compute_closures_by_week(),
            "closures_by_day": compute_closures_by_day(),
            "installs_periods": periods,
        },
        "installs_by_month": installs_by_month,
        "installs_by_week": installs_by_week,
        "installs_by_day_partner": compute_installs_by_partner(),
    }
