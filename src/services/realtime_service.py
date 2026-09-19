import os
import httpx
from src.core.constants import SUPABASE_URL, SUPABASE_KEY
from src.core.logger import logger

_sync_client: httpx.Client | None = None
_sync_client_pid: int | None = None

_async_client: httpx.AsyncClient | None = None
_async_client_pid: int | None = None


def _get_sync_client() -> httpx.Client:
    global _sync_client, _sync_client_pid
    current_pid = os.getpid()
    if _sync_client is None or _sync_client.is_closed or _sync_client_pid != current_pid:
        _sync_client_pid = current_pid
        _sync_client = httpx.Client(
            timeout=5.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _sync_client


def _get_async_client() -> httpx.AsyncClient:
    global _async_client, _async_client_pid
    current_pid = os.getpid()
    if _async_client is None or _async_client.is_closed or _async_client_pid != current_pid:
        _async_client_pid = current_pid
        _async_client = httpx.AsyncClient(
            timeout=5.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _async_client


async def broadcast_task_status(task_id: str, status: str, data: dict = None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase URL o Key no configurados. Omitiendo broadcast.")
        return
        
    url = f"{SUPABASE_URL}/realtime/v1/api/broadcast"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messages": [{
            "topic": f"task:{task_id}",
            "event": "status_changed",
            "payload": {
                "task_id": task_id,
                "status": status,
                **(data or {})
            },
        }]
    }
    
    try:
        client = _get_async_client()
        response = await client.post(url, headers=headers, json=payload, timeout=5.0)
        if response.status_code >= 400:
            logger.warning(
                f"Error de broadcast a Supabase Realtime ({response.status_code}): {response.text}"
            )
        else:
            logger.info(f"Broadcast enviado exitosamente para tarea {task_id} (estado: {status}).")
    except Exception as e:
        logger.error(f"Fallo al emitir broadcast de realtime para tarea {task_id}: {e}")


def broadcast_task_status_sync(task_id: str, status: str, data: dict = None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
        
    url = f"{SUPABASE_URL}/realtime/v1/api/broadcast"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messages": [{
            "topic": f"task:{task_id}",
            "event": "status_changed",
            "payload": {
                "task_id": task_id,
                "status": status,
                **(data or {})
            },
        }]
    }
    
    try:
        client = _get_sync_client()
        response = client.post(url, headers=headers, json=payload, timeout=5.0)
        if response.status_code >= 400:
            logger.warning(
                f"Error de broadcast síncrono ({response.status_code}): {response.text}"
            )
    except Exception as e:
        logger.error(f"Fallo al emitir broadcast síncrono para tarea {task_id}: {e}")
