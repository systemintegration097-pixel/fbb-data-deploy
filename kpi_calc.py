"""
kpi_calc.py — Replica en Python los KPIs de "WO INCIDENT REPORT - 2026" (hoja "KPI 2026",
pestañas "KPI: Monthly" y "KPI: weekly"), calculados 100% a partir de las WOs de GNOC que
ya tenemos descargadas en work_orders (gnoc.db), sin depender de leer los KPIs ya calculados
del Sheet en tiempo de consulta.

Lo único que se trae del Sheet son tablas de REFERENCIA que no existen en el portal GNOC
(mismo patrón que 'List of Boxes' para branch en process_data.py):
  - ZONAS: mapeo Site code -> Branch (la hoja NO usa el branch de Tableau/NIMS que usamos
    en el resto del dashboard, usa su propio mapeo por ZONAS; para que estos KPIs cuadren
    con los que ya reporta el negocio, replicamos ESE mapeo exacto).
  - Staff: días de garantía por técnico instalador (vtp_username -> warranty_days).
  - TWMS: fecha de instalación y técnico instalador por cuenta.
  - Active customers / Incident satisfaction rate: se llenan a mano cada mes en el Sheet
    (Incident satisfaction viene de un dashboard Tableau aparte); se leen tal cual del
    Sheet porque no hay forma de derivarlos de GNOC.
Estas tablas de referencia se cachean en gnoc.db (kpi_zonas_map, kpi_staff_warranty,
kpi_twms, kpi_active_customers, kpi_incident_satisfaction) vía refresh_reference_data(),
para no tener que leer ~55k filas del Sheet en cada consulta de KPI.

Fórmulas replicadas (ver columnas AB-AR de la pestaña GNOC del Sheet):
  AB = resolution_days = closed_time - create_time (días), o "Pending" si no está cerrada
  AC (KPI Closing)     = Pending / On time(<=1d) / > 24H(1-2d) / > 48H(2-3d) / > 72H(>3d)
  AJ (Hours)            = 24 * (closed_time - create_time), o 24*(now - create_time) si abierta
  AK (Mes/año)          = mes de create_time, "mm/yyyy"
  AH (period semanal)   = semana lunes-domingo de create_time, "dd/mm-dd/mm"
  AE (Branch)           = XLOOKUP(site_code, ZONAS.site_code, ZONAS.branch)
  AN (Install Date)     = XLOOKUP(account, TWMS.account, TWMS.install_date)
  AO (<15 días post-inst)= "Complains within 15 days" si (create_time - install_date) < 15
  AP (Warranty)         = "NO WARRANTY" si no hay install_date; si no, "Apply"/"No Apply"
                           según (create_time - install_date) <= warranty_days del instalador
  AQ/AR (Recurring)      = 2+ WOs de la misma cuenta en una ventana de 30 días -> "Recurring
                           within 30 days" (se cuenta como 1 incidente recurrente, no cada
                           repetición por separado -mismo criterio AQ="2" del Sheet)
"""
import os
import sqlite3
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_PATH, "gnoc.db")
KPI_SPREADSHEET_ID = "1Bdoy0F6dVH-iV7cZYIpW2Wn5ondnrWSdxHhUiMbiF_k"
SERVICE_ACCOUNT_JSON = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    os.path.join(BASE_PATH, "google_service_account.json")
)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

MONTH_NAMES_ES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                   "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

BRANCHES = ["ARE", "CAJ", "CUS", "HUN", "JUN", "LAL", "LI1", "LI2", "LI3", "LI4", "LI7", "PIU", "SAN"]

CLOSED_STATUSES = ("close", "closed", "closed ft", "ft completed")


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _gs_client():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    return gspread.authorize(creds)


# ─────────────────────────────────────────────────────────────────────────────
#  REFERENCIA (ZONAS / Staff / TWMS / Active customers / Incident satisfaction)
# ─────────────────────────────────────────────────────────────────────────────
def refresh_reference_data():
    """Vuelve a leer las tablas de referencia desde el Sheet 'KPI 2026' y las cachea en
    gnoc.db. No se llama en cada consulta de KPI -solo cuando hace falta actualizar el
    mapeo de branches/garantías (ver /api/kpi/refresh_reference)."""
    gc = _gs_client()
    sh = gc.open_by_key(KPI_SPREADSHEET_ID)
    conn = _get_conn()
    cur = conn.cursor()

    # ZONAS: columna C = Branch, columna L = Site code (physical)
    zonas_ws = sh.worksheet("ZONAS")
    zonas_rows = zonas_ws.get("C2:L", value_render_option="FORMATTED_VALUE")
    zonas_pairs = [(r[9].strip(), r[0].strip()) for r in zonas_rows if len(r) >= 10 and r[9] and r[0]]
    cur.execute("DELETE FROM kpi_zonas_map")
    cur.executemany("INSERT OR REPLACE INTO kpi_zonas_map (site_code, branch) VALUES (?, ?)", zonas_pairs)

    # Staff: columna H = VTP username, columna C = Warranty period (days)
    staff_ws = sh.worksheet("Staff")
    staff_rows = staff_ws.get("C2:H", value_render_option="FORMATTED_VALUE")
    staff_pairs = []
    for r in staff_rows:
        if len(r) >= 6 and r[5] and r[0]:
            try:
                days = float(str(r[0]).replace(",", "."))
            except ValueError:
                continue
            staff_pairs.append((r[5].strip(), days))
    cur.execute("DELETE FROM kpi_staff_warranty")
    cur.executemany("INSERT OR REPLACE INTO kpi_staff_warranty (vtp_username, warranty_days) VALUES (?, ?)", staff_pairs)

    # TWMS: columna A = Account, columna N = installer username, columna Q = install date
    twms_ws = sh.worksheet("TWMS")
    twms_rows = twms_ws.get("A2:Q", value_render_option="FORMATTED_VALUE")
    twms_triples = []
    for r in twms_rows:
        if len(r) >= 1 and r[0]:
            account = r[0].strip()
            installer = r[13].strip() if len(r) >= 14 and r[13] else ""
            install_date = r[16].strip() if len(r) >= 17 and r[16] else ""
            twms_triples.append((account, install_date, installer))
    cur.execute("DELETE FROM kpi_twms")
    cur.executemany("INSERT OR REPLACE INTO kpi_twms (account, install_date, installer_username) VALUES (?, ?, ?)", twms_triples)

    # Active customers (KPI: Monthly!O9:Z9) e Incident satisfaction (KPI: Monthly!O14:Z14)
    monthly_ws = sh.worksheet("KPI: Monthly")
    active_row = monthly_ws.get("O9:Z9", value_render_option="FORMATTED_VALUE")
    satisf_row = monthly_ws.get("O14:Z14", value_render_option="FORMATTED_VALUE")
    active_vals = active_row[0] if active_row else []
    satisf_vals = satisf_row[0] if satisf_row else []

    cur.execute("DELETE FROM kpi_active_customers")
    cur.execute("DELETE FROM kpi_incident_satisfaction")
    for i, month_name in enumerate(MONTH_NAMES_ES):
        month_key = f"2026-{i+1:02d}"
        if i < len(active_vals) and active_vals[i]:
            try:
                qty = int(float(str(active_vals[i]).replace(",", "")))
                cur.execute("INSERT OR REPLACE INTO kpi_active_customers (month_key, qty) VALUES (?, ?)", (month_key, qty))
            except ValueError:
                pass
        if i < len(satisf_vals) and satisf_vals[i]:
            try:
                rate = float(str(satisf_vals[i]).replace("%", "").replace(",", "."))
                if rate > 1:
                    rate = rate / 100
                cur.execute("INSERT OR REPLACE INTO kpi_incident_satisfaction (month_key, rate) VALUES (?, ?)", (month_key, rate))
            except ValueError:
                pass

    cur.execute("INSERT OR REPLACE INTO kpi_reference_meta (key, value) VALUES ('last_refresh', ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
    conn.close()
    return {
        "zonas": len(zonas_pairs),
        "staff": len(staff_pairs),
        "twms": len(twms_triples),
        "active_customers": len(active_vals),
        "incident_satisfaction": len(satisf_vals),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  ENRIQUECIMIENTO POR WO (replica columnas AB-AR de la pestaña GNOC del Sheet)
# ─────────────────────────────────────────────────────────────────────────────
_ENRICHED_CACHE = {"df": None, "ts": None}
_ENRICHED_CACHE_TTL_SEC = 300


def invalidate_cache():
    """Se llama desde server.py apenas termina un sync exitoso (botón manual o el
    programado run_full_sync.py), para que la página de KPI no muestre datos de hasta
    5 minutos de antigüedad justo después de sincronizar."""
    _ENRICHED_CACHE["df"] = None
    _ENRICHED_CACHE["ts"] = None


def _load_enriched_wos(use_cache=True):
    """Carga work_orders + referencia y devuelve un DataFrame con una fila por WO y las
    columnas derivadas necesarias para todos los KPIs (branch, kpi_closing, hours,
    month_key, week_key, within_15_days, warranty_apply, is_recurring_event).
    Se cachea en memoria unos minutos: el paso de detección de recurrencia es O(n) por
    cuenta y no vale la pena repetirlo en cada request de la página de KPIs (que pide
    mensual + semanal + tendencia por separado)."""
    if use_cache and _ENRICHED_CACHE["df"] is not None:
        age = (datetime.now() - _ENRICHED_CACHE["ts"]).total_seconds()
        if age < _ENRICHED_CACHE_TTL_SEC:
            return _ENRICHED_CACHE["df"]

    import pandas as pd

    conn = _get_conn()
    wos = pd.read_sql_query("""
        SELECT wo_code, account, site_code, create_time, closed_time, wo_status, is_error
        FROM work_orders
        WHERE is_error = 0 AND create_time IS NOT NULL AND create_time != ''
    """, conn)
    zonas = pd.read_sql_query("SELECT site_code, branch FROM kpi_zonas_map", conn)
    twms = pd.read_sql_query("SELECT account, install_date, installer_username FROM kpi_twms", conn)
    staff = pd.read_sql_query("SELECT vtp_username, warranty_days FROM kpi_staff_warranty", conn)
    conn.close()

    wos["create_time"] = pd.to_datetime(wos["create_time"], errors="coerce")
    wos["closed_time"] = pd.to_datetime(wos["closed_time"], errors="coerce")
    wos = wos.dropna(subset=["create_time"])

    zonas = zonas.drop_duplicates(subset=["site_code"])
    wos = wos.merge(zonas, on="site_code", how="left")
    wos["branch"] = wos["branch"].fillna("")

    twms = twms.drop_duplicates(subset=["account"])
    wos = wos.merge(twms, on="account", how="left")
    wos["install_date"] = pd.to_datetime(wos["install_date"], errors="coerce", dayfirst=True)

    staff = staff.drop_duplicates(subset=["vtp_username"])
    wos = wos.merge(staff, left_on="installer_username", right_on="vtp_username", how="left")

    is_closed = wos["closed_time"].notna()
    now = pd.Timestamp(datetime.now())
    elapsed = pd.Series(pd.NaT, index=wos.index, dtype="timedelta64[ns]")
    elapsed[is_closed] = wos.loc[is_closed, "closed_time"] - wos.loc[is_closed, "create_time"]
    elapsed[~is_closed] = now - wos.loc[~is_closed, "create_time"]
    wos["hours"] = elapsed.dt.total_seconds() / 3600.0
    resolution_days = elapsed.dt.total_seconds() / 86400.0

    def _kpi_closing(row_closed, days):
        if not row_closed:
            return "Pending"
        if days <= 1:
            return "On time"
        if days <= 2:
            return "> 24H"
        if days <= 3:
            return "> 48H"
        return "> 72H"

    wos["kpi_closing"] = [
        _kpi_closing(c, d) for c, d in zip(is_closed, resolution_days)
    ]

    wos["month_key"] = wos["create_time"].dt.strftime("%Y-%m")
    # Semana lunes-domingo (misma convención que GNOC!AH: TEXT(L-WEEKDAY(L,2)+1,"dd/mm") & "-" & ...)
    week_monday = wos["create_time"] - pd.to_timedelta(wos["create_time"].dt.weekday, unit="D")
    wos["week_key"] = week_monday.dt.strftime("%Y-%m-%d")

    has_install = wos["install_date"].notna()
    days_since_install = (wos["create_time"] - wos["install_date"]).dt.total_seconds() / 86400.0
    wos["within_15_days"] = has_install & (days_since_install < 15)

    warranty_apply = pd.Series("NO WARRANTY", index=wos.index)
    can_check = has_install & wos["warranty_days"].notna()
    warranty_apply[can_check] = [
        "Apply" if d <= wd else "No Apply"
        for d, wd in zip(days_since_install[can_check], wos.loc[can_check, "warranty_days"])
    ]
    warranty_apply[has_install & ~wos["warranty_days"].notna()] = "No Apply"
    wos["warranty_apply"] = warranty_apply

    # Recurring: 2+ WOs de la misma cuenta en ventana de 30 días -> se cuenta como 1
    # incidente recurrente en el WO donde la cuenta ALCANZA su 2da ocurrencia (mismo
    # criterio que el Sheet con AQ="2", para no contar cada repetición por separado).
    wos = wos.sort_values("create_time").reset_index(drop=True)
    wos["is_recurring_event"] = False
    for account, group in wos.groupby("account"):
        times = group["create_time"].values
        idxs = group.index.values
        count_in_window = []
        j = 0
        for i in range(len(times)):
            while times[i] - times[j] > pd.Timedelta(days=30):
                j += 1
            count_in_window.append(i - j + 1)
        for k, cnt in enumerate(count_in_window):
            if cnt == 2:
                wos.loc[idxs[k], "is_recurring_event"] = True

    _ENRICHED_CACHE["df"] = wos
    _ENRICHED_CACHE["ts"] = datetime.now()
    return wos


def _to_pct(numerator, denominator):
    return (numerator / denominator) if denominator else 0.0


def _empty_kpi_summary():
    return {
        "qty_complains": 0, "ksub_min_per_10ksub": 0.0, "ksub_min_per_10ksub_day": None,
        "resolve_time_hrs": 0.0, "complain_per_10k_day": 0.0, "incident_satisfaction_rate": None,
        "recurrings_per_10k_day": 0.0, "complain_within_15_day": 0.0,
        "warranty_rate": 0.0, "incident_resolve_on_time_rate": 0.0, "recurring_rate": 0.0,
        "active_customers": None,
    }


def _compute_period(df_period, days_in_period, active_customers, incident_satisfaction_rate):
    """Dado el subconjunto de WOs de un período (mes o semana) ya filtrado, calcula todas
    las tablas y el resumen de 11 KPIs, replicando exactamente las fórmulas del Sheet."""
    total_wo = len(df_period)

    branch_table = []
    for br in BRANCHES:
        sub = df_period[df_period["branch"] == br]
        n = len(sub)
        on_time = (sub["kpi_closing"] == "On time").sum()
        h24 = (sub["kpi_closing"] == "> 24H").sum()
        h48 = (sub["kpi_closing"] == "> 48H").sum()
        h72 = (sub["kpi_closing"] == "> 72H").sum()
        d = _to_pct(on_time, n)
        e = _to_pct(h24, n) + d
        f = _to_pct(h48, n) + e
        g = _to_pct(h72, n) + f
        branch_table.append({
            "branch": br, "total_wo": n,
            "under_24h": d, "under_48h": e, "under_72h": f, "over": g,
            "qty_pending": round((1 - g) * n) if n else 0,
            "sum_hours": round(sub["hours"].sum(), 2),
        })

    on_time_total = (df_period["kpi_closing"] == "On time").sum()
    h24_total = (df_period["kpi_closing"] == "> 24H").sum()
    h48_total = (df_period["kpi_closing"] == "> 48H").sum()
    h72_total = (df_period["kpi_closing"] == "> 72H").sum()
    d_total = _to_pct(on_time_total, total_wo)
    e_total = _to_pct(h24_total, total_wo) + d_total
    f_total = _to_pct(h48_total, total_wo) + e_total
    g_total = _to_pct(h72_total, total_wo) + f_total

    total_hours = df_period["hours"].sum()
    warranty_apply_count = (df_period["warranty_apply"] == "Apply").sum()
    within_15_count = df_period["within_15_days"].sum()
    recurring_count = int(df_period["is_recurring_event"].sum())

    summary = _empty_kpi_summary()
    summary["qty_complains"] = total_wo
    summary["resolve_time_hrs"] = round(total_hours, 2)
    summary["incident_resolve_on_time_rate"] = d_total
    summary["recurring_rate"] = _to_pct(recurring_count, total_wo)
    summary["warranty_rate"] = _to_pct(warranty_apply_count, total_wo)
    summary["complain_within_15_day"] = _to_pct(within_15_count, total_wo)
    summary["incident_satisfaction_rate"] = incident_satisfaction_rate
    summary["active_customers"] = active_customers

    if active_customers:
        ksub_min = ((total_hours * 60) / 1000) / (active_customers / 10000)
        summary["ksub_min_per_10ksub"] = round(ksub_min, 2)
        summary["complain_per_10k_day"] = round(_to_pct(total_wo, active_customers / 10000) / days_in_period, 2)
        summary["recurrings_per_10k_day"] = round(_to_pct(recurring_count, active_customers / 10000) / days_in_period, 2)
        if days_in_period != 7:
            summary["ksub_min_per_10ksub_day"] = round(ksub_min / days_in_period, 2)

    recurring_by_branch = []
    for br in BRANCHES:
        sub = df_period[df_period["branch"] == br]
        n = len(sub)
        rec = int(sub["is_recurring_event"].sum())
        recurring_by_branch.append({
            "branch": br, "recurring_count": rec,
            "recurring_rate": _to_pct(rec, n),
        })

    return {
        "total_wo": total_wo,
        "branch_table": branch_table,
        "total_row": {
            "total_wo": total_wo, "under_24h": d_total, "under_48h": e_total,
            "under_72h": f_total, "over": g_total,
            "qty_pending": round((1 - g_total) * total_wo) if total_wo else 0,
        },
        "sum_hours_total": round(total_hours, 2),
        "summary": summary,
        "recurring_by_branch": recurring_by_branch,
        "recurring_total": recurring_count,
    }


def compute_monthly_kpis(month_key):
    """month_key: 'YYYY-MM', ej. '2026-07'."""
    wos = _load_enriched_wos()
    df_period = wos[wos["month_key"] == month_key]

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT qty FROM kpi_active_customers WHERE month_key = ?", (month_key,))
    row = cur.fetchone()
    active_customers = row["qty"] if row else None
    cur.execute("SELECT rate FROM kpi_incident_satisfaction WHERE month_key = ?", (month_key,))
    row = cur.fetchone()
    incident_satisfaction = row["rate"] if row else None
    conn.close()

    year, month = int(month_key[:4]), int(month_key[5:7])
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]

    result = _compute_period(df_period, days_in_month, active_customers, incident_satisfaction)
    result["month_key"] = month_key
    result["month_name"] = MONTH_NAMES_ES[month - 1]
    return result


def compute_weekly_kpis(week_start):
    """week_start: 'YYYY-MM-DD' (lunes de la semana)."""
    wos = _load_enriched_wos()
    df_period = wos[wos["week_key"] == week_start]

    month_key = week_start[:7]
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT qty FROM kpi_active_customers WHERE month_key = ?", (month_key,))
    row = cur.fetchone()
    active_customers = row["qty"] if row else None
    cur.execute("SELECT rate FROM kpi_incident_satisfaction WHERE month_key = ?", (month_key,))
    row = cur.fetchone()
    incident_satisfaction = row["rate"] if row else None
    conn.close()

    result = _compute_period(df_period, 7, active_customers, incident_satisfaction)
    monday = datetime.strptime(week_start, "%Y-%m-%d")
    sunday = monday + timedelta(days=6)
    result["week_key"] = week_start
    result["week_label"] = f"{monday.strftime('%d/%m')}-{sunday.strftime('%d/%m')}"
    return result


def get_available_periods():
    """Meses y semanas para los que ya tenemos datos locales suficientes (para poblar los
    selectores del front-end)."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT strftime('%Y-%m', create_time) as m
        FROM work_orders
        WHERE is_error = 0 AND create_time IS NOT NULL AND create_time != ''
        ORDER BY m
    """)
    months = [r["m"] for r in cur.fetchall() if r["m"]]
    conn.close()

    import pandas as pd
    wos = _load_enriched_wos()
    weeks = sorted(wos["week_key"].dropna().unique().tolist())
    week_options = []
    for w in weeks:
        monday = datetime.strptime(w, "%Y-%m-%d")
        sunday = monday + timedelta(days=6)
        week_options.append({"week_key": w, "label": f"{monday.strftime('%d/%m')}-{sunday.strftime('%d/%m')}"})

    month_options = [{"month_key": m, "label": f"{MONTH_NAMES_ES[int(m[5:7])-1]} {m[:4]}"} for m in months]
    return {"months": month_options, "weeks": week_options}


def compute_trend():
    """Serie mensual (para los meses con datos locales) de Qty Complains, Ksub*min/10Ksub,
    Incident resolve on time rate y WO created by month -para las 3 gráficas de tendencia."""
    wos = _load_enriched_wos()
    months = sorted(wos["month_key"].dropna().unique().tolist())

    conn = _get_conn()
    cur = conn.cursor()
    active_map, satisf_map = {}, {}
    for r in cur.execute("SELECT month_key, qty FROM kpi_active_customers"):
        active_map[r["month_key"]] = r["qty"]
    for r in cur.execute("SELECT month_key, rate FROM kpi_incident_satisfaction"):
        satisf_map[r["month_key"]] = r["rate"]
    conn.close()

    import calendar
    trend = []
    for month_key in months:
        year, month = int(month_key[:4]), int(month_key[5:7])
        days_in_month = calendar.monthrange(year, month)[1]
        df_period = wos[wos["month_key"] == month_key]
        r = _compute_period(df_period, days_in_month, active_map.get(month_key), satisf_map.get(month_key))
        trend.append({
            "month_key": month_key,
            "month_name": MONTH_NAMES_ES[month - 1],
            "qty_complains": r["summary"]["qty_complains"],
            "ksub_min_per_10ksub": r["summary"]["ksub_min_per_10ksub"],
            "incident_resolve_on_time_rate": r["summary"]["incident_resolve_on_time_rate"],
        })
    return trend


def compute_weekly_trend():
    """Serie semanal (lunes-domingo, para las semanas con datos locales -al menos desde
    julio) de Qty Complains, Ksub*min/10Ksub e Incident resolve on time rate (=% de WOs
    resueltas dentro de las 24h, bucket 'On time'; ver AC/KPI Closing en GNOC) -para
    comparar semana a semana en la vista Semanal de la página KPI."""
    wos = _load_enriched_wos()
    weeks = sorted(wos["week_key"].dropna().unique().tolist())

    conn = _get_conn()
    cur = conn.cursor()
    active_map, satisf_map = {}, {}
    for r in cur.execute("SELECT month_key, qty FROM kpi_active_customers"):
        active_map[r["month_key"]] = r["qty"]
    for r in cur.execute("SELECT month_key, rate FROM kpi_incident_satisfaction"):
        satisf_map[r["month_key"]] = r["rate"]
    conn.close()

    trend = []
    for week_key in weeks:
        month_key = week_key[:7]
        df_period = wos[wos["week_key"] == week_key]
        r = _compute_period(df_period, 7, active_map.get(month_key), satisf_map.get(month_key))
        monday = datetime.strptime(week_key, "%Y-%m-%d")
        sunday = monday + timedelta(days=6)
        trend.append({
            "week_key": week_key,
            "week_label": f"{monday.strftime('%d/%m')}-{sunday.strftime('%d/%m')}",
            "qty_complains": r["summary"]["qty_complains"],
            "ksub_min_per_10ksub": r["summary"]["ksub_min_per_10ksub"],
            "incident_resolve_on_time_rate": r["summary"]["incident_resolve_on_time_rate"],
        })
    return trend


def get_reference_status():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM kpi_reference_meta WHERE key = 'last_refresh'")
    row = cur.fetchone()
    last_refresh = row["value"] if row else None
    counts = {}
    for tbl in ("kpi_zonas_map", "kpi_staff_warranty", "kpi_twms", "kpi_active_customers", "kpi_incident_satisfaction"):
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        counts[tbl] = cur.fetchone()[0]
    conn.close()
    return {"last_refresh": last_refresh, "counts": counts}
