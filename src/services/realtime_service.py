"""
Servicio de Realtime Broadcast para PostFast.
Permite emitir eventos en canales de Supabase Realtime desde rutinas de backend.
"""
import httpx
from src.core.constants import SUPABASE_URL, SUPABASE_KEY
from src.core.logger import logger

async def broadcast_task_status(task_id: str, status: str, data: dict = None):
    """
    Emite un evento broadcast vía Supabase Realtime API para notificar el progreso de una tarea.
    Permite comunicación push en tiempo real hacia el frontend (Next.js) sin recurrir a polling HTTP.
    """
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
        async with httpx.AsyncClient() as client:
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
    """
    Versión sincrónica de broadcast_task_status para ser utilizada en workers Celery
    donde el bucle de eventos asíncronos puede estar ausente o no gestionado directamente.
    """
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
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, timeout=5.0)
            if response.status_code >= 400:
                logger.warning(
                    f"Error de broadcast síncrono ({response.status_code}): {response.text}"
                )
    except Exception as e:
        logger.error(f"Fallo al emitir broadcast síncrono para tarea {task_id}: {e}")
