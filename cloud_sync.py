"""
cloud_sync.py — puente HTTP entre este dashboard local y la app en la nube
(cloud_app/) donde los encargados de sucursal completan el comentario de
sus despliegues pendientes.

Si la nube no responde o no está configurada, esto NUNCA debe romper el
sync local: todo error se atrapa y se loguea, nunca se propaga.
"""
import os
import threading

import requests

CLOUD_SYNC_URL = os.environ.get("CLOUD_SYNC_URL", "").rstrip("/")
CLOUD_API_KEY = os.environ.get("CLOUD_API_KEY", "")
REQUEST_TIMEOUT_SEC = 15

_comments_lock = threading.Lock()
_comments_cache = {}  # account -> {branch, comment, status, comment_updated_by, comment_updated_at}


def is_configured():
    return bool(CLOUD_SYNC_URL and CLOUD_API_KEY)


def _headers():
    return {"X-API-Key": CLOUD_API_KEY, "Content-Type": "application/json"}


def push_clients(clients):
    """Sube la lista fresca de despliegues pendientes a la nube (full-refresh:
    la nube desactiva ahí mismo cualquier cuenta que ya no venga en la lista,
    sin perder el comentario que un encargado ya haya dejado)."""
    if not is_configured():
        return {"ok": False, "error": "cloud sync no configurado (CLOUD_SYNC_URL/CLOUD_API_KEY)"}
    try:
        resp = requests.post(
            f"{CLOUD_SYNC_URL}/api/sync/push",
            json={"clients": clients},
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"[cloud_sync] push OK: {result}")
        return result
    except Exception as e:
        print(f"[cloud_sync] push FALLÓ (no afecta el sync local): {e}")
        return {"ok": False, "error": str(e)}


def pull_comments():
    """Trae los comentarios de encargados desde la nube y refresca el cache en
    memoria que lee get_cached_comments(). Nunca lanza excepción: si falla, se
    conserva el cache anterior tal cual estaba."""
    if not is_configured():
        return
    try:
        resp = requests.get(
            f"{CLOUD_SYNC_URL}/api/sync/comments",
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        comments = resp.json().get("comments", [])
        fresh = {c["account"]: c for c in comments if c.get("account")}
        with _comments_lock:
            _comments_cache.clear()
            _comments_cache.update(fresh)
    except Exception as e:
        print(f"[cloud_sync] pull de comentarios FALLÓ (se conserva el cache anterior): {e}")


def get_cached_comments():
    with _comments_lock:
        return dict(_comments_cache)
