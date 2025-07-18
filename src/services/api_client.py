import requests
import streamlit as st
from src.core.logger import logger
from typing import Dict, Any, Optional
import datetime

try:
    from src.core.constants import FASTAPI_URL
except ImportError:
    FASTAPI_URL = "http://localhost:8000"
    print(f"WARN: Default FASTAPI_URL: {FASTAPI_URL}")

def _get_current_token() -> Optional[str]:
    """
    Safely retrieves the current access token from Streamlit's session state.
    This is the ONLY place that should know the structure of st.session_state.
    """
    # Buscamos el token de la plataforma conectada actualmente.
    # Asumimos una lógica simple donde solo hay una plataforma a la vez.
    if st.session_state.get("li_connected"):
        return st.session_state.get("li_token_data", {}).get("access_token")
    # elif st.session_state.get("fb_connected"):
    #     return st.session_state.get("fb_token_data", {}).get("access_token")
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

# --- Funciones de la API que usan el cliente ---

def trigger_etl(platform: str, account_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """Triggers the ETL process via the FastAPI backend."""
    client = get_api_client()
    etl_endpoint = f"{FASTAPI_URL}/analytics/trigger_etl"
    payload = {
        "platform": platform,
        "account_id": account_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    logger.info(f"Triggering ETL for Organization URN: {account_id}")
    
    # Ya no se pasan los headers explícitamente, el cliente los inyecta.
    response = client.post(etl_endpoint, json=payload)
    response.raise_for_status()
    return response.json()

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Polls the status of a background task."""
    client = get_api_client()
    status_endpoint = f"{FASTAPI_URL}/analytics/tasks/status/{task_id}"
    
    response = client.get(status_endpoint)
    if response.status_code != 404:
        response.raise_for_status()
        
    return response.json()

# def generate_content(
#     tone: str, 
#     query: str, 
#     niche: str, 
#     account_name: str, 
#     link_url: Optional[str] = None
# ) -> str:
#     """Calls the LangGraph backend to generate post content."""
#     client = get_api_client()

#     logger.warning(f"[AI Client] Generating content for: {query} with tone '{tone}' in niche '{niche}' AND client {client}")
#     generation_endpoint = f"{FASTAPI_URL}/content/generate_post"
    
#     payload = {
#         "query": query,
#         "tone": tone, 
#         "niche": niche,
#         "account_name": account_name, 
#         "link_url": link_url
#     }

#     response = client.post(
#         generation_endpoint,
#         json={k: v for k, v in payload.items() if v is not None},
#         timeout=180
#     )
#     response.raise_for_status()
#     result = response.json()
    
#     logger.warning(f"[AI Client] Received response: {result}")

#     # El cliente ahora espera la clave 'final_content' que el backend devuelve
#     if "final_content" not in result or not result["final_content"]:
#         raise ValueError("The AI failed to generate content or returned an empty response.")

#     return result["final_content"]

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