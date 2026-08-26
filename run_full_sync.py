"""
run_full_sync.py — Orquestador del sync completo pensado para correr desatendido (Programador
de Tareas de Windows), sin necesitar que server.py esté corriendo como servicio web.

Reutiliza la misma lógica de orquestación que ya usa el botón "Sincronizar Excel" del
dashboard (server.run_background_sync: descarga GNOC/Tableau/NIMS/CNOC en paralelo, luego
process_data.py, que a su vez corre bras_status_check al final) y le agrega un paso más:
publicar las WOs pendientes sin error en el Google Sheet "INCIDENTS PARTNERS" vía la API
oficial (sheets_push.py), reemplazando el paso que antes se hacía a mano con Claude in Chrome.

Cada corrida queda registrada en logs/full_sync_YYYYMMDD.log además de la salida estándar.
"""
import os
import sys
from datetime import datetime

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_PATH)

LOG_DIR = os.path.join(BASE_PATH, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, f"full_sync_{datetime.now().strftime('%Y%m%d')}.log")


class _Tee:
    """Duplica todo lo escrito en stdout/stderr también al archivo de log del día, para
    poder revisar corridas pasadas sin depender del historial del Programador de Tareas."""
    def __init__(self, stream, log_file):
        self.stream = stream
        self.log_file = log_file

    def write(self, data):
        self.stream.write(data)
        self.log_file.write(data)

    def flush(self):
        self.stream.flush()
        self.log_file.flush()


def main():
    log_file = open(LOG_PATH, "a", encoding="utf-8", errors="replace")
    sys.stdout = _Tee(sys.stdout, log_file)
    sys.stderr = _Tee(sys.stderr, log_file)

    print(f"\n===== [FullSync] Iniciando sync automático — {datetime.now().isoformat(timespec='seconds')} =====", flush=True)

    import server
    import sheets_push

    server.run_background_sync()
    status = dict(server.sync_status)

    if status["state"] == "error":
        print(f"[FullSync] El sync de datos (Excel) falló: {status['message']}", flush=True)
        print("[FullSync] Se omite el push a Google Sheets porque no hay datos frescos confiables.", flush=True)
        print(f"===== [FullSync] Terminado con error — {datetime.now().isoformat(timespec='seconds')} =====", flush=True)
        sys.exit(1)

    print(f"[FullSync] Sync de datos (Excel) OK: {status['message']}", flush=True)

    try:
        pushed = sheets_push.push_pending_valid_to_sheet()
        print(f"[FullSync] Push a Google Sheets OK ({pushed} filas).", flush=True)
    except Exception as e:
        print(f"[FullSync] Push a Google Sheets falló: {e}", flush=True)
        print(f"===== [FullSync] Terminado con error en el push a Sheets — {datetime.now().isoformat(timespec='seconds')} =====", flush=True)
        sys.exit(1)

    try:
        errores = sheets_push.push_marlo_errors_to_sheet()
        print(f"[FullSync] Push de errores de Marlo a ERRORES LVL3 OK ({errores} nuevos).", flush=True)
    except Exception as e:
        print(f"[FullSync] Push de errores de Marlo a ERRORES LVL3 falló: {e}", flush=True)

    print(f"===== [FullSync] Completado con éxito — {datetime.now().isoformat(timespec='seconds')} =====", flush=True)


if __name__ == "__main__":
    main()
