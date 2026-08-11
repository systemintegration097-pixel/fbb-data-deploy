"""
bras_status_check.py — Resolución en vivo de Online Status (ONLINE / NOT ONLINE /
NUNCA TUVO SERVICIO) para las cuentas de work_orders que están en TMs y no bloqueadas
por deuda.

Jerarquía completa (aplicada en process_data.py, este módulo solo cubre el nivel 3):
  1. Cuenta no existe en TMs                        -> CANCEL
  2. Cuenta en TMs con status='2'                    -> BLOCK BY DEBT
  3. Cuenta en TMs con cualquier otro status          -> consulta en vivo al CGI de BRAS
     (este módulo), que responde ONLINE, NOT ONLINE, o -si el sistema BRAS no tiene
     ningún registro de esa cuenta ("Not enough information to telnet bras..." / "Can
     not found bras IP...")- NUNCA TUVO SERVICIO.

Alcance del chequeo en vivo: SOLO cuentas con al menos una WO pendiente (no cerrada).
Verificar en vivo las ~7500 cuentas de TODAS las WOs (incluidas miles ya cerradas) tomaba
~45-50 min; limitarlo a pendientes lo baja a ~700 cuentas (~5 min), que es lo que
realmente importa saber en tiempo real. Para que las WOs cerradas no se queden sin dato,
cada resultado se guarda en 'account_online_status' (caché que persiste entre syncs,
sobrevive al DELETE+INSERT de work_orders); las cerradas reusan ahí el último valor
conocido de su cuenta en vez de perderlo."""
import asyncio
import aiohttp
import sqlite3
import os

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_PATH, "gnoc.db")
BRAS_CHECK_URL = "http://10.121.62.102:8080/backup/cgi-bin/bras_checkuser/bras_checkkick_online.php"

# El CGI de BRAS internamente hace un telnet al equipo real por cada consulta; bajo
# concurrencia alta se satura y devuelve "NOT ONLINE" para cuentas que en realidad están
# ONLINE (confirmado en vivo probando la misma cuenta aislada vs. bajo carga: con 40 y
# con 15 concurrentes fallaba, con 8 todavía fallaba ocasionalmente, con 4 fue confiable
# en varias pruebas). Se prioriza la precisión sobre la velocidad -tarda más (~45-50 min
# para 7000+ cuentas) pero no corrompe resultados.
SEM_GLOBAL = 5
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3


def parse_bras_response(text, account):
    """ONLINE / NOT ONLINE / NUNCA TUVO SERVICIO según el texto de respuesta del CGI, o
    None si la respuesta no trae la línea 'Account: {account}' esperada al inicio -señal
    de que el servidor devolvió una respuesta vacía/mezclada de otra sesión bajo carga,
    en cuyo caso hay que reintentar en vez de confiar en lo que venga después."""
    t = text.upper()
    if f"ACCOUNT: {account.upper()}" not in t:
        return None
    if "NOT ENOUGH INFORMATION" in t or "CAN NOT FOUND BRAS IP" in t:
        return "NUNCA TUVO SERVICIO"
    for line in t.splitlines():
        if "NOT ONLINE" in line:
            return "NOT ONLINE"
        if "ONLINE" in line:
            return "ONLINE"
    # Trae el Account correcto pero ninguna línea de estado reconocible: se trata igual
    # que "sin información" en vez de asumir un estado que no se pudo confirmar.
    return "NUNCA TUVO SERVICIO"


async def _check_one(session, sem, account, bras_ip):
    async with sem:
        url = f"{BRAS_CHECK_URL}?cat=view&acc={account}&domain=&bras={bras_ip}"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                    text = await resp.text(errors="ignore")
                    status = parse_bras_response(text, account)
                    if status is not None:
                        return account, status
                    # Respuesta sin el Account esperado (sesión mezclada/vacía bajo carga)
            except Exception:
                pass
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1.5 * attempt)
        return account, None  # no se pudo verificar con confianza; no tocar el status existente


async def _check_bulk_async(pairs):
    sem = asyncio.Semaphore(SEM_GLOBAL)
    connector = aiohttp.TCPConnector(limit=SEM_GLOBAL)
    results = {}
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "Mozilla/5.0"}) as session:
        tasks = [_check_one(session, sem, acc, bras) for acc, bras in pairs]
        done = 0
        for coro in asyncio.as_completed(tasks):
            account, status = await coro
            if status:
                results[account] = status
            done += 1
            if done % 500 == 0:
                print(f"  [BRAS check] {done}/{len(pairs)} cuentas verificadas...", flush=True)
    return results


CLOSED_STATUSES = ("close", "closed", "closed ft", "ft completed")
_CLOSED_PLACEHOLDERS = ", ".join("?" for _ in CLOSED_STATUSES)


def resolve_online_status_bulk():
    """Resuelve el nivel 3 (ONLINE/NOT ONLINE/NUNCA TUVO SERVICIO) en vivo SOLO para las
    cuentas que tienen al menos una WO pendiente (no cerrada) -es lo único que realmente
    necesita estar al minuto-, actualiza work_orders.online_status para TODAS las WOs de
    esas cuentas (pendientes y cerradas) y guarda cada resultado en la caché persistente
    'account_online_status'. Luego, para las WOs cerradas cuya cuenta no fue parte del
    chequeo en vivo (todas sus WOs están cerradas) y que quedaron con online_status vacío,
    aplica el último valor conocido de esa cuenta desde la caché.
    Se corre DESPUÉS de que process_data.py ya insertó las WOs (con online_status='' para
    estas cuentas), así que este paso solo completa lo que falta."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    pending_filter = f"LOWER(wo.wo_status) NOT IN ({_CLOSED_PLACEHOLDERS})"

    cursor.execute(f"""
        SELECT DISTINCT wo.account AS account, tm.bras AS bras
        FROM work_orders wo
        JOIN tm_subscribers tm ON tm.username = wo.account COLLATE NOCASE
        WHERE tm.status != '2' AND tm.bras IS NOT NULL AND tm.bras != ''
          AND {pending_filter}
    """, CLOSED_STATUSES)
    pairs = [(r["account"], r["bras"]) for r in cursor.fetchall()]

    # En TMs, status != '2', pero sin bras asignado: el propio CGI, al no recibir bras,
    # confirma que no hay forma de verificar -> directamente NUNCA TUVO SERVICIO.
    cursor.execute(f"""
        SELECT DISTINCT wo.account AS account
        FROM work_orders wo
        JOIN tm_subscribers tm ON tm.username = wo.account COLLATE NOCASE
        WHERE tm.status != '2' AND (tm.bras IS NULL OR tm.bras = '')
          AND {pending_filter}
    """, CLOSED_STATUSES)
    no_bras_accounts = [r["account"] for r in cursor.fetchall()]

    print(f"[BRAS check] Verificando estado ONLINE/NOT ONLINE de {len(pairs)} cuentas "
          f"con WO pendiente (esto puede tardar varios minutos)...", flush=True)
    results = asyncio.run(_check_bulk_async(pairs)) if pairs else {}

    for acc in no_bras_accounts:
        results.setdefault(acc, "NUNCA TUVO SERVICIO")

    updated = 0
    for account, status in results.items():
        cursor.execute(
            "UPDATE work_orders SET online_status = ? WHERE account = ? COLLATE NOCASE",
            (status, account)
        )
        updated += cursor.rowcount
        cursor.execute("""
            INSERT INTO account_online_status (account, online_status, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(account) DO UPDATE SET
                online_status = excluded.online_status,
                updated_at = excluded.updated_at
        """, (account, status))

    # WOs cerradas cuya cuenta no tuvo ninguna WO pendiente en este sync (por eso no se
    # verificaron arriba) y que quedaron sin online_status: usar el último valor conocido
    # de esa cuenta en la caché, en vez de dejarlas vacías.
    cursor.execute("""
        UPDATE work_orders
        SET online_status = (
            SELECT online_status FROM account_online_status
            WHERE account_online_status.account = work_orders.account COLLATE NOCASE
        )
        WHERE (online_status IS NULL OR online_status = '')
          AND account IN (SELECT account FROM account_online_status)
    """)
    from_cache = cursor.rowcount

    conn.commit()
    conn.close()
    print(f"[BRAS check] {len(results)} cuentas verificadas en vivo, {updated} filas de work_orders "
          f"actualizadas; {from_cache} filas de WOs cerradas completadas desde caché.", flush=True)
    return len(results)


if __name__ == "__main__":
    resolve_online_status_bulk()
