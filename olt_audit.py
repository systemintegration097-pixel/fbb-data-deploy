"""
olt_audit.py — Motor de Auditoría OLT para integración con el dashboard GNOC.

Basado en OLT AUDITOR v3.1. Provee:
  - run_audit(olts_input_path)  → ejecuta el escaneo completo (bloqueante)
  - audit_status                → dict thread-safe con estado y progreso
  - get_fallas(db, filtros)     → query de fallas activas desde la BD
  - get_cortes(db)              → cortes masivos del último escaneo
"""

import asyncio
import aiohttp
import pandas as pd
import xml.etree.ElementTree as ET
import sqlite3
import os
import threading
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
EMS_URL  = "http://10.121.167.65:20270/services/NeManagementService"
HEADERS  = {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': '""'}

BASE_PATH  = os.path.dirname(os.path.abspath(__file__))
DB_FILE    = os.path.join(BASE_PATH, 'olt_auditoria.db')

PON_RANGE       = range(1, 17)   # 1-1-3-1 … 1-1-3-16
# 30s se quedaba corto para puertos con muchas ONUs -confirmado en vivo: PON con 63
# ONUs (CAL0056OLT01, puerto 10) respondió bien en 47s, pero siempre caía en timeout
# con el límite anterior. No es un puerto colgado, solo una respuesta más pesada.
REQUEST_TIMEOUT = 60
MAX_RETRIES     = 3
RETRY_BACKOFF   = 2.0

SEM_GLOBAL  = 60
SEM_PER_OLT = 4

INACTIVO_DIAS     = 60
CORTE_VENTANA_MIN = 60

ESTADOS_FALLA_OPTICA = {'los', 'losi', 'lofi', 'sf', 'sd', 'down'}
ESTADOS_ENERGIA      = {'power-off', 'poweroff'}
ESTADO_OK            = {'up'}

# ─────────────────────────────────────────────────────────────────────────────
#  ESTADO GLOBAL (thread-safe, consultable desde Flask)
# ─────────────────────────────────────────────────────────────────────────────
_status_lock = threading.Lock()
_audit_execution_lock = threading.Lock()
_cancel_flag = False

audit_status = {
    "state":       "idle",   # "idle" | "scanning" | "done" | "error"
    "progress":    0,         # 0-100
    "done":        0,
    "total":       0,
    "last_scan":   None,      # ISO string
    "n_fallas":    0,
    "n_cortes":    0,
    "n_olts_ok":   0,
    "n_olts_err":  0,
    "message":     "",
}


def _set_status(**kwargs):
    with _status_lock:
        audit_status.update(kwargs)


def _inc_done():
    """Incrementa de forma atómica el progreso, asegurando que nunca supere el 100% ni el total."""
    with _status_lock:
        audit_status['done'] += 1
        t = audit_status['total'] or 1
        d = min(audit_status['done'], t)
        audit_status['progress'] = min(100, max(0, int(100 * d / t)))


def get_olt_db_connection():
    """Retorna una conexión configurada con timeout y modo WAL para evitar bloqueos entre hilos."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


def get_db_stats() -> dict:
    """Calcula las estadísticas globales actuales a partir del último estado de cada OLT en la BD."""
    if not os.path.exists(DB_FILE):
        return {"n_olts_ok": 0, "n_fallas": 0, "n_cortes": 0, "n_olts_err": 0}
    try:
        conn = get_olt_db_connection()
        res = conn.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN onu_id IS NOT NULL THEN olt_name END) as n_olts_ok,
                COUNT(DISTINCT CASE WHEN tipo_falla = 'ERROR' AND onu_id IS NULL THEN olt_name END) as n_olts_err,
                SUM(CASE WHEN es_activo = 1 AND tipo_falla NOT IN ('OK','ERROR','INACTIVO_PROBABLE') AND onu_id IS NOT NULL THEN 1 ELSE 0 END) as n_fallas
            FROM escaneos_latest
        """).fetchone()

        cortes_count = conn.execute("SELECT COUNT(*) FROM cortes_latest").fetchone()[0]
        conn.close()
        return {
            "n_olts_ok": (res["n_olts_ok"] if res else 0) or 0,
            "n_olts_err": (res["n_olts_err"] if res else 0) or 0,
            "n_fallas": (res["n_fallas"] if res else 0) or 0,
            "n_cortes": cortes_count or 0
        }
    except Exception as e:
        print(f"[get_db_stats error] {e}")
        return {"n_olts_ok": 0, "n_fallas": 0, "n_cortes": 0, "n_olts_err": 0}


def get_status() -> dict:
    with _status_lock:
        res = dict(audit_status)
    db_stats = get_db_stats()
    # Las tarjetas del dashboard siempre deben tener las estadísticas reales de la base de datos
    for k in ('n_olts_ok', 'n_fallas', 'n_cortes', 'n_olts_err'):
        if res.get('state') == 'scanning':
            if not res.get(k):
                res[k] = db_stats.get(k, 0)
        else:
            res[k] = db_stats.get(k, res.get(k, 0))
    return res

def cancel_audit():
    global _cancel_flag
    with _status_lock:
        if audit_status['state'] == 'scanning':
            _cancel_flag = True
            audit_status['message'] = "Cancelando escaneo..."


# ─────────────────────────────────────────────────────────────────────────────
#  SOAP
# ─────────────────────────────────────────────────────────────────────────────
def build_soap(olt_ip: str, pon_id: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:nem="http://www.zte.com.cn/accessnetwork/ems/webservice/NeManagementService/">'
        '<soapenv:Header><nem:Authentication>'
        '<userName>ossbitel</userName><password>Ume1!2@3#</password>'
        '</nem:Authentication></soapenv:Header>'
        '<soapenv:Body><nem:OperationRequestInfo>'
        '<operationName>LST-ONUSTATE</operationName>'
        '<operatedObject>'
        f'<param><name>OLTID</name><value>{olt_ip}</value></param>'
        f'<param><name>PONID</name><value>{pon_id}</value></param>'
        '</operatedObject>'
        '<operationParam>'
        '<param><name>VLAN</name><value>35</value></param>'
        '</operationParam>'
        '</nem:OperationRequestInfo></soapenv:Body></soapenv:Envelope>'
    ).encode('utf-8')


def parse_onus(xml_text: str):
    onus = []
    try:
        root = ET.fromstring(xml_text)
        for el in root.iter():
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]
        sc = root.find('.//statusCode')
        if sc is not None and sc.text != "0":
            msg = root.findtext('.//statusDesc') or 'ERR-ZTE'
            return [], f"ERR-ZTE:{msg[:40]}"
        for record in root.findall('.//result/record'):
            item = {
                p.find('name').text: (p.find('value').text or '--')
                for p in record.findall('param')
                if p.find('name') is not None and p.find('value') is not None
            }
            if 'ONUID' in item:
                onus.append(item)
        return onus, "SYS-200"
    except ET.ParseError as e:
        return [], f"ERR-XML:{str(e)[:40]}"
    except Exception as e:
        return [], f"ERR-PARSE:{str(e)[:40]}"


# ─────────────────────────────────────────────────────────────────────────────
#  CLASIFICACIÓN
# ─────────────────────────────────────────────────────────────────────────────
def _parse_ts(ts_str):
    if not ts_str or str(ts_str).strip() in ('--', 'None', '', 'null'):
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
                '%d/%m/%Y %H:%M:%S', '%Y%m%d%H%M%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(str(ts_str).strip(), fmt)
        except ValueError:
            continue
    return None


def clasificar(estado: str, lastofftime_str) -> dict:
    e   = (estado or '').lower().strip()
    ts  = _parse_ts(lastofftime_str)
    now = datetime.now()
    tiene_fecha_reciente = ts is not None and (now - ts).days <= INACTIVO_DIAS

    if e in ESTADO_OK:
        return dict(tipo_falla='OK', prioridad='', analisis='Servicio OK', es_activo=True)
    if e in ESTADOS_ENERGIA:
        return dict(tipo_falla='ENERGIA',
                    prioridad='ALTA' if tiene_fecha_reciente else 'MUY_BAJA',
                    analisis='Sin energía eléctrica (casa cliente)',
                    es_activo=tiene_fecha_reciente)
    if e in ESTADOS_FALLA_OPTICA:
        return dict(tipo_falla='LOS',
                    prioridad='ALTA' if tiene_fecha_reciente else 'MUY_BAJA',
                    analisis='Pérdida de señal óptica (LOS/Fibra)',
                    es_activo=tiene_fecha_reciente)
    if ts is None:
        return dict(tipo_falla='INACTIVO_PROBABLE', prioridad='MUY_BAJA',
                    analisis='Sin fecha de caída — posible cancelado/nunca conectado',
                    es_activo=False)
    if (now - ts).days > INACTIVO_DIAS:
        return dict(tipo_falla='INACTIVO_PROBABLE', prioridad='MUY_BAJA',
                    analisis=f'Sin actividad hace {(now-ts).days}d — posible cancelado',
                    es_activo=False)
    return dict(tipo_falla='OPTICA', prioridad='MEDIA',
                analisis='Falla óptica / desconectado (estado no estándar)',
                es_activo=True)


# ─────────────────────────────────────────────────────────────────────────────
#  WORKER ASYNC
# ─────────────────────────────────────────────────────────────────────────────
def _err_record(olt_name, olt_ip, pon, estado, analisis, status):
    return {
        'OLT': olt_name, 'IP': olt_ip, 'PON': pon,
        'ONU_ID': None, 'SN': None,
        'Estado': estado, 'FECHA_CAIDA': None, 'Dias_Sin_Servicio': None,
        'Tipo_Falla': 'ERROR', 'Prioridad': '',
        'Analisis': analisis, 'es_activo': False,
        'CORTE': '', 'Status_Req': status,
    }


async def query_pon_async(session, sem_global, sem_olt,
                          olt_name, olt_ip, pon) -> list:
    global _cancel_flag
    if _cancel_flag:
        _inc_done()
        return []
    last_err = ''
    try:
        for intento in range(1, MAX_RETRIES + 1):
            if _cancel_flag:
                return []
            async with sem_global:
                if _cancel_flag:
                    return []
                async with sem_olt:
                    if _cancel_flag:
                        return []
                    try:
                        payload = build_soap(olt_ip, pon)
                        async with session.post(
                            EMS_URL, data=payload,
                            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                        ) as resp:
                            if resp.status != 200:
                                return [_err_record(olt_name, olt_ip, pon,
                                                    'ERROR HTTP', f'HTTP {resp.status}',
                                                    str(resp.status))]
                            xml_text = await resp.text()
                            onus, status = parse_onus(xml_text)
                            result = []
                            for o in onus:
                                estado = o.get('OperState', 'unknown')
                                loft   = o.get('LASTOFFTIME', None)
                                cls    = clasificar(estado, loft)
                                ts     = _parse_ts(loft)
                                dias_off = (datetime.now() - ts).days if ts else None
                                result.append({
                                    'OLT':             olt_name,
                                    'IP':              olt_ip,
                                    'PON':             pon,
                                    'ONU_ID':          o.get('ONUID'),
                                    'SN':              o.get('AUTHINFO'),
                                    'Estado':          estado,
                                    'FECHA_CAIDA':     loft,
                                    'Dias_Sin_Servicio': dias_off,
                                    'Tipo_Falla':      cls['tipo_falla'],
                                    'Prioridad':       cls['prioridad'],
                                    'Analisis':        cls['analisis'],
                                    'es_activo':       cls['es_activo'],
                                    'CORTE':           '',
                                    'Status_Req':      status,
                                })
                            return result

                    except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                        last_err = f'TIMEOUT(intento {intento}/{MAX_RETRIES})'
                    except aiohttp.ClientConnectorError as e:
                        last_err = f'CONN-ERR:{str(e)[:50]}'
                    except Exception as e:
                        last_err = f'EXC:{str(e)[:60]}'

            if intento < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF * intento)

        return [_err_record(olt_name, olt_ip, pon, 'TIMEOUT', last_err, 'TIMEOUT')]
    finally:
        _inc_done()


# ─────────────────────────────────────────────────────────────────────────────
#  DETECCIÓN DE CORTES
# ─────────────────────────────────────────────────────────────────────────────
def detect_cortes(all_records: list) -> tuple:
    cortes = []
    grupos = defaultdict(list)
    for idx, r in enumerate(all_records):
        if r['es_activo'] and r['Tipo_Falla'] not in ('OK', 'ERROR', 'INACTIVO_PROBABLE'):
            grupos[(r['OLT'], r['IP'], r['PON'])].append((idx, r))

    for (olt_name, olt_ip, pon), items in grupos.items():
        por_tipo = defaultdict(list)
        for idx, r in items:
            por_tipo[r['Tipo_Falla']].append((idx, r))

        for tipo_falla, grupo in por_tipo.items():
            if len(grupo) < 2:
                continue
            con_ts, sin_ts = [], []
            for idx, r in grupo:
                ts = _parse_ts(r['FECHA_CAIDA'])
                (con_ts if ts else sin_ts).append((idx, r, ts))
            con_ts.sort(key=lambda x: x[2])
            i = 0
            while i < len(con_ts):
                ventana = [con_ts[i]]
                for j in range(i + 1, len(con_ts)):
                    if (con_ts[j][2] - con_ts[i][2]).total_seconds() / 60 <= CORTE_VENTANA_MIN:
                        ventana.append(con_ts[j])
                    else:
                        break
                if len(ventana) >= 2:
                    tipo_corte = 'CORTE-ENERGIA' if tipo_falla == 'ENERGIA' else 'CORTE-LOS'
                    hora_corte = ventana[0][2].strftime('%Y-%m-%d %H:%M')
                    for idx, r, _ in ventana:
                        all_records[idx]['CORTE'] = f'! {tipo_corte}'
                    cortes.append({
                        'OLT': olt_name, 'IP': olt_ip, 'PON': pon,
                        'Tipo_Corte': tipo_corte,
                        'Hora_Corte': hora_corte,
                        'ONUs_Afectadas': len(ventana),
                        'Causa': ('Corte de energía eléctrica'
                                  if tipo_falla == 'ENERGIA'
                                  else 'Pérdida de señal óptica (fibra/LOS)'),
                        'ONUs_IDs': ', '.join(v[1]['ONU_ID'] or '' for v in ventana),
                    })
                    i += len(ventana)
                else:
                    i += 1
            if len(sin_ts) >= 2:
                tipo_corte = 'CORTE-ENERGIA' if tipo_falla == 'ENERGIA' else 'CORTE-LOS'
                for idx, r, _ in sin_ts:
                    all_records[idx]['CORTE'] = f'! {tipo_corte} (sin-ts)'
                cortes.append({
                    'OLT': olt_name, 'IP': olt_ip, 'PON': pon,
                    'Tipo_Corte': tipo_corte + '-SIN-TS',
                    'Hora_Corte': 'No disponible',
                    'ONUs_Afectadas': len(sin_ts),
                    'Causa': 'Corte probable — sin timestamp exacto',
                    'ONUs_IDs': ', '.join(r['ONU_ID'] or '' for _, r, _ in sin_ts),
                })
    return all_records, cortes


# ─────────────────────────────────────────────────────────────────────────────
#  BASE DE DATOS
# ─────────────────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()


CORTES_RETENTION_DIAS = 30

def init_db():
    conn = get_olt_db_connection()
    conn.executescript("""
        -- Histórico crudo de escaneos. YA NO se escribe aquí (ver flush_to_db) -crecía
        -- ~4.7 millones de filas/día porque el loop 24/7 insertaba una fila nueva por
        -- ONU en CADA ciclo sin ningún borrado, hasta llegar a 33M filas / 8.7GB en una
        -- semana. Nada en el código leía esa historia -todas las consultas del dashboard
        -- solo necesitan "el último estado por OLT"-, así que se reemplazó por
        -- escaneos_latest (una sola fila vigente por OLT+PON+ONU, se pisa cada ciclo).
        -- La tabla se deja aquí (vacía) por compatibilidad, no se elimina el esquema.
        CREATE TABLE IF NOT EXISTS escaneos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_scan TEXT, olt_name TEXT, olt_ip TEXT, pon TEXT,
            onu_id TEXT, sn TEXT, estado TEXT, lastofftime TEXT,
            dias_sin_servicio INTEGER, tipo_falla TEXT, prioridad TEXT,
            es_activo INTEGER, status_req TEXT, corte TEXT
        );
        CREATE TABLE IF NOT EXISTS escaneos_latest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_scan TEXT, olt_name TEXT, olt_ip TEXT, pon TEXT,
            onu_id TEXT, sn TEXT, estado TEXT, lastofftime TEXT,
            dias_sin_servicio INTEGER, tipo_falla TEXT, prioridad TEXT,
            es_activo INTEGER, status_req TEXT, corte TEXT
        );
        CREATE TABLE IF NOT EXISTS cortes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_detectado TEXT, olt_name TEXT, olt_ip TEXT, pon TEXT,
            tipo_corte TEXT, hora_corte TEXT, onus_afectadas INTEGER,
            causa TEXT, onus_ids TEXT
        );
        CREATE TABLE IF NOT EXISTS cortes_latest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_detectado TEXT, olt_name TEXT, olt_ip TEXT, pon TEXT,
            tipo_corte TEXT, hora_corte TEXT, onus_afectadas INTEGER,
            causa TEXT, onus_ids TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_cortes_ts ON cortes(olt_name, ts_detectado);
        CREATE INDEX IF NOT EXISTS ix_cortes   ON cortes(olt_name, pon);
        CREATE INDEX IF NOT EXISTS ix_latest_olt ON escaneos_latest(olt_name);
        CREATE INDEX IF NOT EXISTS ix_latest_olt_pon ON escaneos_latest(olt_name, pon);
        CREATE INDEX IF NOT EXISTS ix_latest_activo ON escaneos_latest(es_activo, tipo_falla);
        CREATE INDEX IF NOT EXISTS ix_latest_cortes_olt ON cortes_latest(olt_name);
    """)
    conn.commit()
    conn.close()


def flush_to_db(records, cortes, ts_scan):
    rows_e = [
        (ts_scan, r['OLT'], r['IP'], r['PON'], r['ONU_ID'], r['SN'],
         r['Estado'], r['FECHA_CAIDA'], r.get('Dias_Sin_Servicio'),
         r['Tipo_Falla'], r['Prioridad'], int(r.get('es_activo', 0)),
         r['Status_Req'], r.get('CORTE', ''))
        for r in records if r.get('ONU_ID') or r.get('Tipo_Falla') == 'ERROR'
    ]
    rows_c = [
        (ts_scan, c['OLT'], c['IP'], c['PON'], c['Tipo_Corte'],
         c['Hora_Corte'], c['ONUs_Afectadas'], c['Causa'], c['ONUs_IDs'])
        for c in cortes
    ]
    # OLTs que se escanearon en este ciclo (puede ser un subconjunto si fue un escaneo
    # manual parcial): solo el estado "latest" de ESTAS OLTs se reemplaza, dejando intacto
    # el de las demás.
    olts_in_batch = sorted({r['OLT'] for r in records})

    with _db_lock:
        conn = get_olt_db_connection()
        if olts_in_batch:
            conn.executemany(
                "DELETE FROM escaneos_latest WHERE olt_name = ?",
                [(o,) for o in olts_in_batch])
            # Los cortes también se reemplazan por OLT (no solo se insertan los nuevos):
            # así, si una OLT ya no tiene un corte masivo activo este ciclo, deja de
            # aparecer como "vigente" en vez de quedar pegada para siempre.
            conn.executemany(
                "DELETE FROM cortes_latest WHERE olt_name = ?",
                [(o,) for o in olts_in_batch])
        if rows_e:
            conn.executemany(
                "INSERT INTO escaneos_latest VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows_e)
        if rows_c:
            conn.executemany(
                "INSERT INTO cortes VALUES (NULL,?,?,?,?,?,?,?,?,?)", rows_c)
            conn.executemany(
                "INSERT INTO cortes_latest VALUES (NULL,?,?,?,?,?,?,?,?,?)", rows_c)
        # Retención del log histórico de cortes (evento, bajo volumen): se poda para que
        # no crezca indefinidamente, pero se conserva más tiempo que escaneos_latest
        # porque sí tiene valor como historial de incidentes.
        conn.execute(
            "DELETE FROM cortes WHERE ts_detectado < datetime('now', ?)",
            (f'-{CORTES_RETENTION_DIAS} days',))
        conn.commit()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  ORQUESTADOR ASYNC
# ─────────────────────────────────────────────────────────────────────────────
async def _run_async(df_olts: pd.DataFrame) -> list:
    global _cancel_flag
    sem_global = asyncio.Semaphore(SEM_GLOBAL)
    sems_olt = {}
    for _, row in df_olts.iterrows():
        ip = row['OLT_IP']
        if ip not in sems_olt:
            sems_olt[ip] = asyncio.Semaphore(SEM_PER_OLT)

    connector = aiohttp.TCPConnector(
        limit=SEM_GLOBAL + 20,
        limit_per_host=6,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
        keepalive_timeout=30,
    )
    all_results = []
    async with aiohttp.ClientSession(connector=connector, headers=HEADERS) as session:
        tasks = [
            query_pon_async(
                session, sem_global, sems_olt[row['OLT_IP']],
                row['OLT_NAME'], row['OLT_IP'], f"1-1-3-{p_num}"
            )
            for _, row in df_olts.iterrows()
            for p_num in PON_RANGE
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                print(f"[OLT Audit] Excepción no capturada: {r}")
            elif isinstance(r, list):
                all_results.extend(r)
    return all_results


async def _run_retry_async(failed_items: list) -> list:
    """Segunda pasada al final del ciclo: reconsulta SOLO los (OLT, IP, PON) que
    quedaron en TIMEOUT tras los 3 intentos normales de query_pon_async. La mayoría
    de estos son blips transitorios de carga en el EMS (60 consultas SOAP concurrentes,
    24/7) que se resuelven solos si se reconsultan un rato después, sin tener que
    esperar al siguiente ciclo completo de miles de consultas."""
    sem_global = asyncio.Semaphore(SEM_GLOBAL)
    sems_olt = {}
    for _, ip, _ in failed_items:
        if ip not in sems_olt:
            sems_olt[ip] = asyncio.Semaphore(SEM_PER_OLT)

    connector = aiohttp.TCPConnector(
        limit=SEM_GLOBAL + 20,
        limit_per_host=6,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
        keepalive_timeout=30,
    )
    results = []
    async with aiohttp.ClientSession(connector=connector, headers=HEADERS) as session:
        tasks = [
            query_pon_async(session, sem_global, sems_olt[ip], olt_name, ip, pon)
            for olt_name, ip, pon in failed_items
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for r in gathered:
            if isinstance(r, Exception):
                print(f"[OLT Audit] Excepción no capturada en reintento final: {r}")
            elif isinstance(r, list):
                results.extend(r)
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  FUNCIÓN PRINCIPAL (llamada desde server.py en un thread)
# ─────────────────────────────────────────────────────────────────────────────
def run_audit(olts_input_path: str, selected_olts: list = None):
    """
    Ejecuta el escaneo completo o parcial. Bloquea el thread hasta terminar.
    Actualiza audit_status durante la ejecución.
    Garantiza exclusión mutua para que no se solapen escaneos automáticos y manuales.
    """
    global _cancel_flag

    if not _audit_execution_lock.acquire(blocking=False):
        print("[OLT Audit] Ya hay un escaneo en ejecución. Omitiendo invocación concurrente.", flush=True)
        return

    try:
        _cancel_flag = False

        _set_status(state='scanning', progress=0, done=0, total=0,
                    message='Inicializando entorno...')

        if not os.path.exists(olts_input_path):
            _set_status(state='error', message=f'Archivo no encontrado: {olts_input_path}')
            return

        df_olts = pd.read_excel(olts_input_path)
        required = {'OLT_NAME', 'OLT_IP'}
        if not required.issubset(set(df_olts.columns)):
            _set_status(state='error',
                        message=f'El archivo debe tener columnas: {required}. '
                                f'Encontradas: {list(df_olts.columns)}')
            return
            
        if selected_olts is not None and len(selected_olts) > 0:
            df_olts = df_olts[df_olts['OLT_NAME'].isin(selected_olts)]
            if df_olts.empty:
                _set_status(state='error', message='Ninguna OLT seleccionada se encontró en el archivo.')
                return

        # Eliminar posibles duplicados
        df_olts = df_olts.drop_duplicates(subset=['OLT_NAME', 'OLT_IP'])

        total_tasks = len(df_olts) * len(PON_RANGE)
        _set_status(done=0, total=total_tasks, progress=0, message=f'Escaneando {len(df_olts)} OLTs × 16 Puertos...')

        init_db()
        ts_scan = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        _set_status(message='Ejecutando consultas asíncronas en paralelo...')
        all_records = asyncio.run(_run_async(df_olts))

        if _cancel_flag:
            _set_status(state='idle', message='Escaneo cancelado por el usuario.', progress=0)
            return

        # Segunda pasada: reintentar solo los puertos que quedaron en TIMEOUT (ver
        # análisis del 2026-08-20 -0.065% de las consultas, esparcidas entre 37 OLTs,
        # sin patrón por número de puerto -> blips transitorios de carga en el EMS,
        # no equipos realmente caídos. Reconsultarlos ahora evita esperar el siguiente
        # ciclo completo para que se resuelvan solos.
        failed = [(r['OLT'], r['IP'], r['PON']) for r in all_records if r.get('Status_Req') == 'TIMEOUT']
        if failed and not _cancel_flag:
            _set_status(message=f'Reintentando {len(failed)} puertos que quedaron en timeout...')
            retry_results = asyncio.run(_run_retry_async(failed))
            retry_by_key = {}
            for r in retry_results:
                retry_by_key.setdefault((r['OLT'], r['IP'], r['PON']), []).append(r)

            new_all_records = []
            replaced_keys = set()
            for r in all_records:
                key = (r['OLT'], r['IP'], r['PON'])
                if r.get('Status_Req') == 'TIMEOUT' and key in retry_by_key:
                    if key not in replaced_keys:
                        new_all_records.extend(retry_by_key[key])
                        replaced_keys.add(key)
                    continue
                new_all_records.append(r)
            all_records = new_all_records

            n_resueltos = sum(
                1 for rows in retry_by_key.values()
                if rows and rows[0].get('Status_Req') != 'TIMEOUT'
            )
            print(f"[OLT Audit] Reintento final: {n_resueltos}/{len(failed)} puertos se resolvieron.", flush=True)

        _set_status(message='Detectando cortes masivos...')
        all_records, cortes = detect_cortes(all_records)

        _set_status(message='Guardando en base de datos...')
        flush_to_db(all_records, cortes, ts_scan)

        # Estadísticas finales
        n_fallas = sum(1 for r in all_records
                       if r.get('es_activo') and r['Tipo_Falla'] not in ('OK', 'ERROR', 'INACTIVO_PROBABLE')
                       and r.get('ONU_ID'))
        n_olts_ok  = len(set(r['OLT'] for r in all_records if r.get('ONU_ID')))
        n_olts_err = len(set(r['OLT'] for r in all_records
                             if r['Tipo_Falla'] == 'ERROR' and not r.get('ONU_ID')))

        _set_status(
            state='done',
            progress=100,
            done=total_tasks,
            last_scan=ts_scan,
            n_fallas=n_fallas,
            n_cortes=len(cortes),
            n_olts_ok=n_olts_ok,
            n_olts_err=n_olts_err,
            message=f'Escaneo completado: {n_fallas} fallas, {len(cortes)} cortes masivos',
        )

    except Exception as e:
        _set_status(state='error', message=f'Error durante el escaneo: {str(e)}')
        raise
    finally:
        _audit_execution_lock.release()


# ─────────────────────────────────────────────────────────────────────────────
#  QUERIES PARA EL DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
def get_fallas(filtro_olt='', filtro_tipo='', filtro_prioridad='', limit=500) -> list:
    """Retorna ONUs en falla activa del último escaneo de cada OLT."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = get_olt_db_connection()
        where = [
            "es_activo = 1",
            "tipo_falla NOT IN ('OK','INACTIVO_PROBABLE','ERROR')",
            "onu_id IS NOT NULL"
        ]
        params = []

        if filtro_olt:
            where.append("olt_name LIKE ?")
            params.append(f'%{filtro_olt}%')
        if filtro_tipo:
            where.append("tipo_falla = ?")
            params.append(filtro_tipo.upper())
        if filtro_prioridad:
            where.append("prioridad = ?")
            params.append(filtro_prioridad.upper())

        sql = f"""
            SELECT olt_name, olt_ip, pon, onu_id, sn, estado,
                   lastofftime, dias_sin_servicio, tipo_falla,
                   prioridad, corte
            FROM escaneos_latest
            WHERE {' AND '.join(where)}
            ORDER BY prioridad DESC, olt_name, pon
            LIMIT ?
        """
        params.append(limit)
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[get_fallas error] {e}")
        return []


def get_cortes(limit=200) -> list:
    """Retorna cortes masivos del escaneo más reciente de cada OLT."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = get_olt_db_connection()
        rows = conn.execute("""
            SELECT olt_name, olt_ip, pon, tipo_corte, hora_corte,
                   onus_afectadas, causa, onus_ids
            FROM cortes_latest
            ORDER BY onus_afectadas DESC LIMIT ?
        """, (limit,)).fetchall()
        result = [dict(r) for r in rows]
        conn.close()
        return result
    except Exception as e:
        print(f"[get_cortes error] {e}")
        return []


def get_alarmas(limit=100) -> list:
    """Retorna alarmas de prioridad ALTA del escaneo más reciente por cada OLT, agregadas por OLT+PON."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = get_olt_db_connection()
        rows = conn.execute("""
            SELECT olt_name, olt_ip, pon, tipo_falla,
                   COUNT(*) as total_onus,
                   COUNT(CASE WHEN corte LIKE '!%' THEN 1 END) as en_corte
            FROM escaneos_latest
            WHERE es_activo = 1
                  AND prioridad = 'ALTA'
                  AND tipo_falla NOT IN ('OK','ERROR','INACTIVO_PROBABLE')
                  AND onu_id IS NOT NULL
            GROUP BY olt_name, olt_ip, pon, tipo_falla
            ORDER BY en_corte DESC, total_onus DESC
            LIMIT ?
        """, (limit,)).fetchall()
        result = [dict(r) for r in rows]
        conn.close()
        return result
    except Exception as e:
        print(f"[get_alarmas error] {e}")
        return []


def get_resumen_olts() -> list:
    """Resumen por OLT del escaneo más reciente por cada OLT."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = get_olt_db_connection()
        rows = conn.execute("""
            SELECT olt_name, olt_ip,
                SUM(CASE WHEN tipo_falla='OK' THEN 1 ELSE 0 END) as ok,
                SUM(CASE WHEN tipo_falla IN ('LOS','OPTICA') AND es_activo=1 THEN 1 ELSE 0 END) as los,
                SUM(CASE WHEN tipo_falla='ENERGIA' AND es_activo=1 THEN 1 ELSE 0 END) as energia,
                SUM(CASE WHEN tipo_falla='INACTIVO_PROBABLE' THEN 1 ELSE 0 END) as inactivo,
                SUM(CASE WHEN tipo_falla='ERROR' THEN 1 ELSE 0 END) as error_pons
            FROM escaneos_latest
            GROUP BY olt_name, olt_ip
            ORDER BY (los + energia) DESC, olt_name
        """).fetchall()
        result = [dict(r) for r in rows]
        conn.close()
        return result
    except Exception as e:
        print(f"[get_resumen_olts error] {e}")
        return []


def get_olt_errors() -> list:
    """Retorna las OLTs que tuvieron errores o falta de respuesta en su escaneo más reciente."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = get_olt_db_connection()
        rows = conn.execute("""
            SELECT olt_name, olt_ip, pon, status_req, ts_scan
            FROM escaneos_latest
            WHERE tipo_falla = 'ERROR'
            ORDER BY olt_name, pon
        """).fetchall()

        olts_dict = {}
        for r in rows:
            name = r['olt_name']
            if name not in olts_dict:
                status = r['status_req'] or "ERROR DESCONOCIDO"
                category = "TIMEOUT"
                desc = "Tiempo de espera agotado al consultar el PON en EMS"
                if "The NE does not exist" in status:
                    category = "NE_NOT_EXIST"
                    desc = "La OLT no existe o no está registrada en el EMS ZTE"
                elif "The NE is not connected" in status:
                    category = "NE_DISCONNECTED"
                    desc = "La OLT está registrada pero desconectada/offline del EMS"
                elif "TIMEOUT" in status:
                    category = "TIMEOUT"
                    desc = "Timeout de conexión al consultar el PON en EMS"
                else:
                    category = "OTRO"
                    desc = status

                olts_dict[name] = {
                    "olt_name": name,
                    "olt_ip": r['olt_ip'],
                    "category": category,
                    "category_desc": desc,
                    "status_sample": status,
                    "ts_scan": r['ts_scan'],
                    "error_count": 0,
                    "error_pons": []
                }
            olts_dict[name]["error_count"] += 1
            olts_dict[name]["error_pons"].append({
                "pon": r['pon'],
                "status": r['status_req']
            })

        conn.close()
        return list(olts_dict.values())
    except Exception as e:
        print(f"[get_olt_errors error] {e}")
        return []


def get_olt_detail(olt_name: str) -> dict:
    """Retorna el detalle completo y desglose por PON de una OLT específica."""
    if not os.path.exists(DB_FILE) or not olt_name:
        return None
    try:
        conn = get_olt_db_connection()
        rows = conn.execute("""
            SELECT olt_name, olt_ip, pon, onu_id, sn, estado, lastofftime, dias_sin_servicio,
                   tipo_falla, prioridad, es_activo, status_req, corte, ts_scan
            FROM escaneos_latest
            WHERE olt_name = ?
            ORDER BY pon, CAST(onu_id AS INTEGER), onu_id
        """, (olt_name,)).fetchall()

        if not rows:
            conn.close()
            return None

        olt_ip = rows[0]['olt_ip']
        ts_scan = rows[0]['ts_scan']

        cortes = conn.execute("""
            SELECT pon, tipo_corte, hora_corte, onus_afectadas, causa, onus_ids
            FROM cortes_latest
            WHERE olt_name = ?
        """, (olt_name,)).fetchall()

        conn.close()

        pons_dict = {}
        total_ok = 0
        total_los = 0
        total_energia = 0
        total_inactivo = 0
        total_errors = 0
        onus_list = []

        for r in rows:
            pon = r['pon'] or "N/A"
            if pon not in pons_dict:
                pons_dict[pon] = {
                    "pon": pon,
                    "total": 0,
                    "ok": 0,
                    "los": 0,
                    "energia": 0,
                    "inactivo": 0,
                    "error": 0,
                    "error_msg": ""
                }

            tf = r['tipo_falla']
            if tf == 'OK':
                pons_dict[pon]['ok'] += 1
                total_ok += 1
            elif tf in ('LOS', 'OPTICA') and r['es_activo']:
                pons_dict[pon]['los'] += 1
                total_los += 1
            elif tf == 'ENERGIA' and r['es_activo']:
                pons_dict[pon]['energia'] += 1
                total_energia += 1
            elif tf == 'INACTIVO_PROBABLE':
                pons_dict[pon]['inactivo'] += 1
                total_inactivo += 1
            elif tf == 'ERROR':
                pons_dict[pon]['error'] += 1
                total_errors += 1
                pons_dict[pon]['error_msg'] = r['status_req'] or "ERROR"

            if r['onu_id']:
                pons_dict[pon]['total'] += 1
                onus_list.append(dict(r))

        return {
            "olt_name": olt_name,
            "olt_ip": olt_ip,
            "ts_scan": ts_scan,
            "summary": {
                "total_onus": len(onus_list),
                "ok": total_ok,
                "los": total_los,
                "energia": total_energia,
                "inactivo": total_inactivo,
                "error_pons": total_errors,
                "cortes_count": len(cortes)
            },
            "pons": sorted(
                pons_dict.values(),
                key=lambda p: int(p["pon"].rsplit("-", 1)[-1]) if p["pon"].rsplit("-", 1)[-1].isdigit() else 999
            ),
            "cortes": [dict(c) for c in cortes],
            "onus": onus_list[:500]
        }
    except Exception as e:
        print(f"[get_olt_detail error] {e}")
        return None


def get_olt_port_status(olt_name: str, pon_port_num, onu_id: str = None) -> dict:
    """Retorna el estado (del último escaneo) de un puerto PON específico de una
    OLT -esta es la misma información que ya recolecta el loop de escaneo continuo,
    así que responde al instante sin tener que ir en vivo a ningún portal externo.
    Si se pasa onu_id, además señala cuál de las ONUs del puerto es la del cliente."""
    if not os.path.exists(DB_FILE) or not olt_name or not pon_port_num:
        return None
    pon_code = f"1-1-3-{pon_port_num}"
    try:
        conn = get_olt_db_connection()
        rows = conn.execute("""
            SELECT olt_name, olt_ip, pon, onu_id, sn, estado, lastofftime, dias_sin_servicio,
                   tipo_falla, prioridad, es_activo, status_req, ts_scan
            FROM escaneos_latest
            WHERE olt_name = ? AND pon = ?
            ORDER BY CAST(onu_id AS INTEGER), onu_id
        """, (olt_name, pon_code)).fetchall()
        conn.close()

        if not rows:
            return None

        onus = []
        ok = los = energia = inactivo = error = 0
        client_onu = None
        for r in rows:
            tf = r['tipo_falla']
            if tf == 'OK':
                ok += 1
            elif tf in ('LOS', 'OPTICA') and r['es_activo']:
                los += 1
            elif tf == 'ENERGIA' and r['es_activo']:
                energia += 1
            elif tf == 'INACTIVO_PROBABLE':
                inactivo += 1
            elif tf == 'ERROR':
                error += 1

            item = {
                "onu_id": r['onu_id'],
                "sn": r['sn'],
                "estado": r['estado'],
                "tipo_falla": tf,
                "prioridad": r['prioridad'],
                "dias_sin_servicio": r['dias_sin_servicio'],
                "lastofftime": r['lastofftime']
            }
            onus.append(item)
            if onu_id and r['onu_id'] and str(r['onu_id']) == str(onu_id):
                client_onu = item

        return {
            "olt_name": olt_name,
            "olt_ip": rows[0]['olt_ip'],
            "pon": pon_code,
            "pon_num": pon_port_num,
            "ts_scan": rows[0]['ts_scan'],
            "total_onus": len(onus),
            "ok": ok,
            "los": los,
            "energia": energia,
            "inactivo": inactivo,
            "error": error,
            "onus": onus,
            "client_onu": client_onu
        }
    except Exception as e:
        print(f"[get_olt_port_status error] {e}")
        return None


async def _query_one_port_live(olt_name: str, olt_ip: str, pon_code: str) -> list:
    """Consulta EN VIVO al EMS un solo puerto PON (1 llamada SOAP, no 6400) -para cuando
    se necesita el estado actual YA, sin esperar a que el loop continuo llegue a esa OLT
    (un ciclo completo de 400 OLTs puede tardar bastante)."""
    connector = aiohttp.TCPConnector(limit=4)
    async with aiohttp.ClientSession(connector=connector, headers=HEADERS) as session:
        sem_global = asyncio.Semaphore(1)
        sem_olt = asyncio.Semaphore(1)
        return await query_pon_async(session, sem_global, sem_olt, olt_name, olt_ip, pon_code)


def get_olt_port_status_live(olt_name: str, pon_port_num, onu_id: str = None) -> dict:
    """Como get_olt_port_status, pero consulta el EMS EN VIVO para ese único puerto en vez
    de leer el último escaneo del loop continuo -responde en 1-3s típicamente (vs. esperar
    hasta que el ciclo de 6400 puertos llegue a esta OLT). De paso, actualiza
    escaneos_latest con el resultado fresco para que el resto del dashboard (ficha de OLT,
    resúmenes) también se beneficie de este dato al instante."""
    if not olt_name or not pon_port_num:
        return None
    pon_code = f"1-1-3-{pon_port_num}"

    # OLT IP: se toma de escaneos_latest (ya lo conocemos de algún escaneo previo) en vez
    # de leer el excel de OLTs en cada consulta.
    conn = get_olt_db_connection()
    row = conn.execute(
        "SELECT olt_ip FROM escaneos_latest WHERE olt_name = ? LIMIT 1", (olt_name,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    olt_ip = row['olt_ip']

    try:
        records = asyncio.run(_query_one_port_live(olt_name, olt_ip, pon_code))
    except Exception as e:
        print(f"[get_olt_port_status_live error] {e}")
        conn.close()
        return None

    ts_scan = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows_e = [
        (ts_scan, r['OLT'], r['IP'], r['PON'], r['ONU_ID'], r['SN'],
         r['Estado'], r['FECHA_CAIDA'], r.get('Dias_Sin_Servicio'),
         r['Tipo_Falla'], r['Prioridad'], int(r.get('es_activo', 0)),
         r['Status_Req'], '')
        for r in records if r.get('ONU_ID') or r.get('Tipo_Falla') == 'ERROR'
    ]
    with _db_lock:
        if rows_e:
            conn.execute("DELETE FROM escaneos_latest WHERE olt_name = ? AND pon = ?", (olt_name, pon_code))
            conn.executemany(
                "INSERT INTO escaneos_latest VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows_e)
            conn.commit()
    conn.close()

    onus, ok, los, energia, inactivo, error = [], 0, 0, 0, 0, 0
    client_onu = None
    for r in records:
        tf = r['Tipo_Falla']
        if tf == 'OK':
            ok += 1
        elif tf in ('LOS', 'OPTICA') and r.get('es_activo'):
            los += 1
        elif tf == 'ENERGIA' and r.get('es_activo'):
            energia += 1
        elif tf == 'INACTIVO_PROBABLE':
            inactivo += 1
        elif tf == 'ERROR':
            error += 1
        if not r.get('ONU_ID'):
            continue
        item = {
            "onu_id": r['ONU_ID'],
            "sn": r['SN'],
            "estado": r['Estado'],
            "tipo_falla": tf,
            "prioridad": r['Prioridad'],
            "dias_sin_servicio": r.get('Dias_Sin_Servicio'),
            "lastofftime": r['FECHA_CAIDA'],
        }
        onus.append(item)
        if onu_id and str(r['ONU_ID']) == str(onu_id):
            client_onu = item

    return {
        "olt_name": olt_name,
        "olt_ip": olt_ip,
        "pon": pon_code,
        "pon_num": pon_port_num,
        "ts_scan": ts_scan,
        "total_onus": len(onus),
        "ok": ok,
        "los": los,
        "energia": energia,
        "inactivo": inactivo,
        "error": error,
        "onus": onus,
        "client_onu": client_onu,
        "live": True,
    }


