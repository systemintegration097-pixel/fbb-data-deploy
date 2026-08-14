"""
deploy_pending.py — Integra la automatización de "deploy ant" (descarga Deploy WO Pending
desde Tableau y lo sube a su propio Google Sheet, ver deploy ant/deploy.py) al dashboard:
- Lee la pestaña "WO Pendiente" de ESE Sheet (vía la cuenta de servicio que ya vive en
  deploy ant/) y arma un resumen por branch para mostrarlo en la página "Despliegues
  pendientes".
- Permite disparar deploy.py como subproceso desde el botón "Actualizar Despliegues" del
  dashboard, en vez de tener que correrlo a mano.
"""
import os
import sys
import subprocess
import threading
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

import cloud_sync

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.join(BASE_PATH, "deploy ant")
DEPLOY_SCRIPT = os.path.join(DEPLOY_DIR, "deploy.py")
LOG_FILE = os.path.join(DEPLOY_DIR, "automatizacion_fbb.log")

SPREADSHEET_ID = "1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA"
SCOPES_RO = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

BRANCHES = ["ARE", "CAJ", "CUS", "HUN", "JUN", "LAL", "LI1", "LI2", "LI3", "LI4", "LI7", "PIU", "SAN"]
DEPLOY_BUCKETS = ["Under 24h", "Over 24h", "Over 48h", "Over 72h"]


def _find_credentials_file():
    if not os.path.isdir(DEPLOY_DIR):
        return None
    for f in os.listdir(DEPLOY_DIR):
        if f.endswith(".json"):
            return os.path.join(DEPLOY_DIR, f)
    return None


def get_summary():
    """Lee 'WO Pendiente' en vivo (vía Sheets API, no vía Excel local) y arma el resumen
    por branch + el listado completo de clientes pendientes."""
    cred_path = _find_credentials_file()
    if not cred_path:
        raise FileNotFoundError("No se encontró el archivo de credenciales de Google en 'deploy ant/'.")

    creds = Credentials.from_service_account_file(cred_path, scopes=SCOPES_RO)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("WO Pendiente")
    rows = ws.get("A2:S")

    clients = []
    for r in rows:
        if len(r) < 4 or not str(r[3]).strip():
            continue
        clients.append({
            "branch": r[1].strip() if len(r) > 1 else "",
            "partner": r[2].strip() if len(r) > 2 else "",
            "account": r[3].strip(),
            "shop_code": r[4].strip() if len(r) > 4 else "",
            "customer_name": r[5].strip() if len(r) > 5 else "",
            # El teléfono llega con comas de separador de miles (formato numérico de
            # Sheets aplicado a una columna que en realidad es texto), se limpia acá.
            "phone": r[6].strip().replace(",", "") if len(r) > 6 else "",
            # Vienen con coma como separador decimal (formato regional de Sheets), no
            # punto -inválido para Leaflet/JS tal cual.
            "lat": r[7].strip().replace(",", ".") if len(r) > 7 else "",
            "lng": r[8].strip().replace(",", ".") if len(r) > 8 else "",
            # VSMART_CREATE_TIME: fecha en la que se creó la venta en el sistema.
            "sale_date": r[12].strip() if len(r) > 12 else "",
            "deployment_type": r[14].strip() if len(r) > 14 else "",
            "pending_days": r[15].strip() if len(r) > 15 else "",
            "ft_code": r[16].strip() if len(r) > 16 else "",
            "connector_code": r[18].strip() if len(r) > 18 else "",
        })

    branch_table = []
    for br in BRANCHES:
        sub = [c for c in clients if c["branch"] == br]
        row = {"branch": br, "total": len(sub)}
        for bucket in DEPLOY_BUCKETS:
            row[bucket] = sum(1 for c in sub if c["deployment_type"] == bucket)
        row["cerrar_wo"] = sum(1 for c in sub if c["pending_days"].strip().lower() == "cerrar wo")
        branch_table.append(row)

    branches_conocidos = set(BRANCHES)
    sin_branch = [c for c in clients if c["branch"] not in branches_conocidos]

    return {
        "total": len(clients),
        "branch_table": branch_table,
        "sin_branch_count": len(sin_branch),
        "clients": clients,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_deploy_run": _get_last_success_time(),
    }


def _get_last_success_time():
    """Busca la última línea 'Fin de automatización (EXITO)' en el log de deploy ant para
    saber cuándo corrió exitosamente por última vez (independiente de si el servidor de
    este dashboard se reinició, a diferencia de guardar solo en memoria)."""
    if not os.path.exists(LOG_FILE):
        return None
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in reversed(lines):
            if "Fin de automatización (EXITO)" in line:
                return line.split(" | ", 1)[0].split(",")[0]
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Disparo de deploy.py como subproceso (botón "Actualizar Despliegues")
# ─────────────────────────────────────────────────────────────────────────────
_run_lock = threading.Lock()
_run_state = {"state": "idle", "message": "", "started_at": None}
_run_proc = None  # Popen del proceso deploy.py activo (para poder cancelarlo)


def get_run_status():
    with _run_lock:
        return dict(_run_state)


def cancel_run():
    """Mata el proceso deploy.py activo (y TODO su árbol -Selenium, geckodriver,
    Firefox-, con 'taskkill /T' en vez de solo el proceso padre). Sin el /T, matar solo
    el python.exe de deploy.py deja a Firefox/geckodriver corriendo huérfanos para
    siempre (fue justo lo que pasó: se acumularon 40+ Firefox de corridas anteriores que
    quedaron vivas al reiniciar este servidor en medio de una corrida)."""
    global _run_proc
    with _run_lock:
        if _run_state["state"] != "running":
            return False
        proc = _run_proc
    if proc is not None and proc.poll() is None:
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                            capture_output=True, timeout=15)
        except Exception as e:
            print(f"[deploy_pending] No se pudo matar el árbol de procesos (PID {proc.pid}): {e}")
    with _run_lock:
        _run_state["state"] = "idle"
        _run_state["message"] = "Actualización cancelada por el usuario."
    return True


def _log_has_fresh_success(since: datetime) -> bool:
    """deploy.py loguea con logging.StreamHandler(), que por defecto escribe a stderr (no
    a stdout) -por eso NO hay que confiar en proc.stdout para saber si salió bien. Lo
    confiable es el archivo de log (RotatingFileHandler, siempre a disco pase lo que
    pase): se busca ahí una línea de éxito con timestamp posterior al inicio de ESTA
    corrida, para no confundirla con el éxito de una corrida anterior."""
    if not os.path.exists(LOG_FILE):
        return False
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in reversed(lines):
            if "Fin de automatización (EXITO)" not in line:
                continue
            try:
                ts = datetime.strptime(line.split(" | ", 1)[0].split(",")[0], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            return ts >= since
    except Exception:
        pass
    return False


RUN_TIMEOUT_SEC = 1800  # 30 min tope de seguridad (Selenium + espera de fórmulas de Sheets)


def _run_worker():
    global _run_state, _run_proc
    inicio = datetime.now()
    proc = None
    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            [sys.executable, "-u", DEPLOY_SCRIPT],
            cwd=DEPLOY_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            env=env,
        )
        with _run_lock:
            _run_proc = proc

        salida_lines = []
        try:
            for line in iter(proc.stdout.readline, ''):
                if line:
                    salida_lines.append(line)
        finally:
            proc.stdout.close()

        try:
            proc.wait(timeout=RUN_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=15)
            with _run_lock:
                _run_state["state"] = "error"
                _run_state["message"] = "Se agotó el tiempo máximo (30 min) esperando la automatización; se detuvo el proceso."
                _run_proc = None
            return

        succeeded = False
        with _run_lock:
            _run_proc = None
            # Si el usuario canceló mientras tanto, no pisar ese estado con un
            # error/éxito que ya no aplica (el proceso murió porque LO matamos).
            if _run_state["state"] != "running":
                return
            if _log_has_fresh_success(inicio):
                _run_state["state"] = "success"
                _run_state["message"] = "Actualización de despliegues completada con éxito."
                succeeded = True
            else:
                tail = "\n".join("".join(salida_lines).strip().splitlines()[-8:])
                _run_state["state"] = "error"
                _run_state["message"] = f"El script terminó sin registrar éxito (código {proc.returncode}): {tail or 'sin salida'}"

        if succeeded:
            # Fuera del lock (una request HTTP no debe bloquear get_run_status()) y
            # nunca debe convertir una corrida local exitosa en un error: si la nube
            # está caída, solo se loguea.
            try:
                resumen = get_summary()
                cloud_sync.push_clients(
                    resumen["clients"],
                    last_deploy_run=resumen.get("last_deploy_run"),
                    checked_at=resumen.get("checked_at"),
                )
            except Exception as e:
                print(f"[deploy_pending] No se pudo subir a la nube (no afecta el resultado local): {e}")
    except Exception as e:
        with _run_lock:
            _run_proc = None
            if _run_state["state"] == "running":
                _run_state["state"] = "error"
                _run_state["message"] = f"No se pudo ejecutar deploy.py: {e}"


def trigger_run():
    """Devuelve False si ya hay una corrida en curso (para no lanzar dos Firefox a la vez)."""
    with _run_lock:
        if _run_state["state"] == "running":
            return False
        _run_state["state"] = "running"
        _run_state["message"] = "Ejecutando automatización (Tableau + Google Sheets)... puede tardar varios minutos."
        _run_state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    threading.Thread(target=_run_worker, daemon=True).start()
    return True
