import requests
import streamlit as st
from src.core.logger import logger
from typing import Dict, Any, Optional, List
import datetime
import uuid
from src.services.supabase_client import get_supabase
from src.services.redis_client import redis_client
from src.supabase_auth import get_aipost_user

try:
    from src.core.constants import FASTAPI_URL
except ImportError:
    FASTAPI_URL = "http://localhost:8000"
    print(f"WARN: Default FASTAPI_URL: {FASTAPI_URL}")

def _get_current_token() -> Optional[str]:
    """
    Obtiene el token de autenticación de LinkedIn.
    1. Busca en la sesión actual de Streamlit (`st.session_state`).
    2. Si no lo encuentra, intenta recuperarlo desde Redis.
    """
    # 1. Probar con el token de la sesión activa de Streamlit
    if st.session_state.get("li_connected"):
        token = (st.session_state.get("li_token_data") or {}).get("access_token")
        if token:
            logger.debug("Token de LinkedIn obtenido desde st.session_state.")
            return token

    #TODO Depurar esto
    
    # 2. Si no está en la sesión, intentar obtenerlo desde Redis
    aipost_user = get_aipost_user()
    if aipost_user and hasattr(aipost_user, 'id'):
        logger.debug(f"Intentando obtener el token de LinkedIn desde Redis.[user_id={aipost_user.id}]")
        token_from_redis = redis_client.get_linkedin_token_from_redis(user_id=aipost_user.id)
        if token_from_redis:
            logger.debug("Token de LinkedIn obtenido desde Redis.")
            # Podrías volver a guardar el token en la sesión aquí si lo necesitas
            st.session_state['li_token_data'] = {'access_token': token_from_redis}
            st.session_state['li_connected'] = True
            return token_from_redis

    logger.warning("No se pudo encontrar un token de LinkedIn válido.")
    return None

# Crear una sesión de requests que inyectará el token en cada llamada.
class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r

def get_api_client() -> requests.Session:
    """
    Returns a requests.Session instance configured with the current
    user's authentication token.
    """
    session = requests.Session()
    access_token = _get_current_token()
    if access_token:
        session.auth = BearerAuth(access_token)
    else:
        # Si no hay token, las llamadas fallarán con 401 en el backend, lo cual es correcto.
        logger.warning("API client initialized without an access token. Calls to protected endpoints will fail.")
    return session


def get_user_profile() -> Optional[Dict[str, Any]]:
    """
    Llama al endpoint /auth/me para obtener los datos del perfil del usuario,
    incluyendo la información de LinkedIn si existe.
    """
    client = get_api_client()
    # Asegurarnos de que el cliente tenga autenticación
    if not client.auth:
        logger.error("Intento de llamar a /auth/me sin un token de autenticación.")
        return None

    endpoint = f"{FASTAPI_URL}/auth/me"
    try:
        response = client.get(endpoint)
        response.raise_for_status()  # Lanza un error para respuestas 4xx/5xx
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"Error HTTP al llamar a /auth/me: {http_err}")
        if http_err.response.status_code == 401:
            st.warning("Tu sesión ha expirado. Por favor, vuelve a iniciar sesión.")
    except Exception as e:
        logger.error(f"Error inesperado al llamar a /auth/me: {e}")
    return None


# --- Funciones de la API que usan el cliente ---
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Conservado solo si se usa para otras tareas no analíticas."""
    # Actualmente no hay endpoint de analytics; devolvemos 404-like structure si se llama.
    logger.warning("get_task_status llamado pero Analytics ha sido eliminado.")
    return {"status": "NOT_FOUND", "result": None, "task_id": task_id}


def start_content_generation(
    tone: str, query: str, niche: str, account_name: str, link_url: Optional[str] = None
) -> str:
    """Inicia la tarea de generación de contenido y devuelve el ID de la tarea."""

    client = get_api_client()
    endpoint = f"{FASTAPI_URL}/content/generate_post"
    payload = {
        "query": query, "tone": tone, "niche": niche,
        "account_name": account_name, "link_url": link_url
    }

    response = client.post(endpoint, json={k: v for k, v in payload.items() if v is not None}, timeout=180)
    response.raise_for_status()
    return response.json()["task_id"]

def get_generation_status(task_id: str) -> Dict[str, Any]:
    """Consulta el estado de una tarea de generación de contenido."""
    client = get_api_client()
    endpoint = f"{FASTAPI_URL}/content/generate_post/status/{task_id}"
    response = client.get(endpoint)
    response.raise_for_status()
    return response.json()


def schedule_or_publish_post(
    platform: str, account_id: str, content: str, 
    scheduled_time: Optional[datetime] = None, link_url: Optional[str] = None
) -> Dict[str, Any]:
    """Schedules or publishes a post via the API."""
    client = get_api_client()
    schedule_endpoint = f"{FASTAPI_URL}/content/schedule_post"
    payload = {
        "platform": platform, "account_id": account_id, "content": content,
        "scheduled_time_str": scheduled_time.isoformat(timespec='seconds') if scheduled_time else None,
        "link_url": link_url
    }
    
    response = client.post(
        schedule_endpoint,
        json={k: v for k, v in payload.items() if v is not None}
    )
    response.raise_for_status()
    return response.json()


def resume_content_generation(task_id: str, feedback: str) -> Dict[str, Any]:
    """Reanuda una tarea de generación de contenido con feedback del usuario."""
    client = get_api_client()
    endpoint = f"{FASTAPI_URL}/content/generate_post/resume"

    payload = {"task_id": task_id, "feedback": feedback}
    response = client.post(endpoint, json=payload)
    response.raise_for_status()

    return response.json()

# --- CRUD para posts ---
def create_post(
    content: str,
    status: str,
    platform: str,
    account_id: str,
    scheduled_time: Optional[datetime] = None,
    published_time: Optional[datetime] = None,
    title: Optional[str] = None,
    feedback: Optional[str] = None,
    image_url: Optional[str] = None,
    link_url: Optional[str] = None
) -> str:
    """Crea un nuevo post y lo guarda en Supabase. Devuelve el id."""
    supabase = get_supabase()
    post_id = str(uuid.uuid4())
    payload = {
        "id": post_id,
        "content": content,
        "status": status,
        "platform": platform,
        "account_id": account_id,
        "scheduled_time": scheduled_time,
        "published_time": published_time,
        "title": title,
        "feedback": feedback,
        "image_url": image_url,
        "link_url": link_url,
    }
    supabase.table("posts").insert({k: v for k, v in payload.items() if v is not None}).execute()
    return post_id

def get_all_posts(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene todos los posts desde Supabase, opcionalmente filtrando por status."""
    supabase = get_supabase()
    query = supabase.table("posts").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data or []

def get_post_by_id(post_id: str) -> Optional[Dict[str, Any]]:
    supabase = get_supabase()
    result = supabase.table("posts").select("*").eq("id", post_id).single().execute()
    return result.data if result.data else None

def update_post(post_id: str, updates: Dict[str, Any]) -> bool:
    """Actualiza los campos de un post dado su id. updates es un dict con los campos a actualizar."""
    if not updates:
        return False
    supabase = get_supabase()
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    if not clean_updates:
        return False
    result = supabase.table("posts").update(clean_updates).eq("id", post_id).execute()
    return bool(result.data)

def delete_post(post_id: str) -> bool:
    supabase = get_supabase()
    result = supabase.table("posts").delete().eq("id", post_id).execute()
    return bool(result.data)