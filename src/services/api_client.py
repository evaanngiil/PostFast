import requests
import streamlit as st
from src.core.logger import logger
from typing import Dict, Any, Optional, List
import datetime
from datetime import datetime as _dt, timezone
import uuid
from src.services.supabase_client import get_supabase_admin as get_supabase
from src.services.redis_client import redis_client
from src.supabase_auth import get_aipost_user

try:
    from src.core.constants import FASTAPI_URL
except ImportError:
    FASTAPI_URL = "http://localhost:8000"
    print(f"ADVERTENCIA: FASTAPI_URL por defecto: {FASTAPI_URL}")

def _get_current_token() -> Optional[str]:
    """
    Obtiene el token de autenticación actual de la plataforma (LinkedIn OAuth).

    Intenta recuperar el token del state interactivo (Streamlit) y hace fallback 
    al store persistente (Redis) para soportar la ejecución background (ej. Celery).

    :returns: Token JWT en formato string, o None si no se encuentra sesión válida.
    """
    # 1. Recuperación en contexto síncrono (UI).
    try:
        if st.session_state.get("li_connected"):
            token = (st.session_state.get("li_token_data") or {}).get("access_token")
            if token:
                logger.debug("Token de LinkedIn obtenido desde st.session_state.")
                return token
    except (RuntimeError, AttributeError):
        # Fallback silencioso cuando el runtime de UI no está presente (workers).
        logger.debug("st.session_state no disponible. Evaluando contexto background.")

    # 2. Recuperación en contexto asíncrono/background (Cache).
    try:
        aipost_user = get_aipost_user()
        if aipost_user and hasattr(aipost_user, 'id'):
            logger.debug(f"Intentando obtener el token de LinkedIn desde Redis.[user_id={aipost_user.id}]")
            token_from_redis = redis_client.get_linkedin_token_from_redis(user_id=aipost_user.id)
            if token_from_redis:
                logger.debug("Token de LinkedIn obtenido desde Redis.")
                # Inyección reactiva en el framework de estado si está disponible.
                try:
                    st.session_state['li_token_data'] = {'access_token': token_from_redis}
                    st.session_state['li_connected'] = True
                except (RuntimeError, AttributeError):
                    pass
                return token_from_redis
    except Exception as e:
        logger.debug(f"Error obteniendo token desde Redis: {e}")

    logger.warning("No se pudo encontrar un token de LinkedIn válido.")
    return None

# Middleware de inyección de autorización Bearer.
class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r

def get_api_client() -> requests.Session:
    """
    Construye una sesión HTTP (requests) pre-inyectada con el token de autorización actual.

    :returns: Instancia configurada de requests.Session.
    """
    session = requests.Session()
    access_token = _get_current_token()
    if access_token:
        session.auth = BearerAuth(access_token)
    else:
        # El rechazo del request se delega al backend mediante 401 Unauthorized.
        logger.warning("Cliente de API inicializado sin token de acceso. Las llamadas a endpoints protegidos fallaran.")
    return session


def get_user_profile() -> Optional[Dict[str, Any]]:
    """
    Realiza un handshake contra el endpoint principal de identity para recuperar los claims del usuario.

    :returns: Diccionario con la metadata del perfil consolidado, o None en fallo.
    """
    client = get_api_client()
    # Prevención de pre-flight calls sin capa de seguridad.
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


# Interfaces con Backend API.
def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Punto de entrada obsoleto. Preservado temporalmente para fallback de rutinas asíncronas no migradas.

    :param task_id: Identificador de la tarea Celery.
    :returns: Payload estructurado de respuesta "NOT_FOUND".
    """
    logger.warning("get_task_status llamado pero Analytics ha sido eliminado.")
    return {"status": "NOT_FOUND", "result": None, "task_id": task_id}


def start_content_generation(
    tone: str, query: str, niche: str, account_name: str, selected_account:dict ,link_url: Optional[str] = None
) -> str:
    """
    Dispatch de una orden de generación hacia el grafo de agentes del backend.

    :param tone: Tonalidad esperada de la publicación.
    :param query: Contexto o prompt primario sobre el que crear contenido.
    :param niche: Segmento o sector objetivo.
    :param account_name: Nombre visible del author/tenant.
    :param selected_account: Diccionario con metadata de la cuenta target.
    :param link_url: Opcional. URL de referencia para ingesta en el grafo.
    :returns: ID de la tarea de Celery encolada.
    """

    client = get_api_client()
    endpoint = f"{FASTAPI_URL}/content/generate_post"
    payload = {
        "query": query, "tone": tone, "niche": niche,
        "account_name": account_name, "selected_account": selected_account, "link_url": link_url
    }

    response = client.post(endpoint, json={k: v for k, v in payload.items() if v is not None}, timeout=180)
    response.raise_for_status()
    return response.json()["task_id"]

def get_generation_status(task_id: str) -> Dict[str, Any]:
    """
    Consulta reactiva del estado del LangGraph broker mediante polling al backend.

    :param task_id: Identificador UUID de la tarea.
    :returns: Diccionario con estado, output serializado y/o prompts pendientes.
    """
    client = get_api_client()
    endpoint = f"{FASTAPI_URL}/content/generate_post/status/{task_id}"
    response = client.get(endpoint)
    response.raise_for_status()
    return response.json()


def schedule_or_publish_post(
    platform: str, account_id: str, content: str, 
    scheduled_time: Optional[datetime] = None, link_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Efectúa el proxy request para encolar o despachar una publicación al instante hacia las redes.

    :param platform: Red social destino (ej: 'linkedin').
    :param account_id: Identificador de la cuenta que publicará (URN de LinkedIn).
    :param content: Cuerpo de texto del post.
    :param scheduled_time: Opcional. Timestamp en UTC de programación diferida.
    :param link_url: Opcional. Metadato de URL a enlazar en el snippet de preview.
    :returns: Payload confirmando inicio/schedule de tarea con su task_id.
    """
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
    """
    Retoma el flujo suspendido de un grafo inyectando un feedback loop validado por el usuario.

    :param task_id: UUID original de la request inicial.
    :param feedback: Prompt rectificativo textual.
    :returns: Nuevo bloque de estado/task_id asignado al proceso reactivado.
    """
    client = get_api_client()
    endpoint = f"{FASTAPI_URL}/content/generate_post/resume"

    payload = {"task_id": task_id, "feedback": feedback}
    response = client.post(endpoint, json=payload)
    response.raise_for_status()

    return response.json()

# Controladores DTO para Gestión de Publicaciones.
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
    """
    Instancia una publicación en la BD relacional y devuelve su primary key UUID.

    :param content: Cuerpo base de la publicación.
    :param status: Estado interno ('draft', 'published', 'scheduled').
    :param platform: Destino nominal ('linkedin').
    :param account_id: Identificador asociado.
    :param scheduled_time: Timestamp de agenda futura.
    :param published_time: Timestamp efectivo de ejecución.
    :param title: Alias de referencia visual interna.
    :param feedback: Log transaccional del review-node.
    :param image_url: Opcional URL del asset de imagen.
    :param link_url: Opcional URl embebida.
    :returns: ID insertado (UUID string).
    """
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

def get_all_posts(status: Optional[str] = None, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera el catálogo histórico de contenido asociado al tenant actual.

    :param status: Filtro por estado ('draft', etc.).
    :param account_id: Filtro exacto por identificador de cuenta (URN).
    :returns: Arreglo de diccionarios representando la tabla posts.
    """
    supabase = get_supabase()
    query = supabase.table("posts").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if account_id:
        query = query.eq("account_id", account_id)
    result = query.execute()
    return result.data or []

def get_post_by_id(post_id: str) -> Optional[Dict[str, Any]]:
    """
    Búsqueda individual mediante Primary Key UUID.

    :param post_id: Cadena identificadora.
    :returns: Documento consolidado del post, o None si no hace hit.
    """
    supabase = get_supabase()
    result = supabase.table("posts").select("*").eq("id", post_id).single().execute()
    return result.data if result.data else None

def update_post(post_id: str, updates: Dict[str, Any]) -> bool:
    """
    Actualización idempotente mediante partial payload para registro específico.

    :param post_id: Puntero de referencia primaria.
    :param updates: Diccionario que abstrae a un objeto Pydantic UpdatePayload filtrado.
    :returns: True si se logró la operación atómica de mutación local.
    """
    if not updates:
        return False
    supabase = get_supabase()
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    if not clean_updates:
        return False
    result = supabase.table("posts").update(clean_updates).eq("id", post_id).execute()
    return bool(result.data)

def delete_post(post_id: str) -> bool:
    """
    Eliminación estructurada o lógica de un post por su puntero primario.

    :param post_id: UUID en string.
    :returns: Confirmación booleana.
    """
    supabase = get_supabase()
    result = supabase.table("posts").delete().eq("id", post_id).execute()
    return bool(result.data)


def get_company_profile(org_urn: str) -> Optional[Dict[str, Any]]:
    """
    Recupera el perfil de empresa almacenado en Supabase para el URN dado.

    :param org_urn: URN corporativo de LinkedIn.
    :returns: Diccionario con la metadata de la organización, o None si no existe.
    """
    try:
        supabase = get_supabase()
        result = (
            supabase.table("company_profiles")
            .select("*")
            .eq("org_urn", org_urn)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error recuperando company_profile para {org_urn}: {e}")
        return None


def is_first_company_connection(org_urn: str) -> bool:
    """
    Evalúa si el tenant corporativo carece de registro histórico en base de datos.
    Utilizado como flag para disparar pipelines de extracción inicial (batch).

    :param org_urn: URN corporativo de LinkedIn.
    :returns: True si la empresa es completamente nueva para el sistema.
    """
    return get_company_profile(org_urn) is None


def save_company_profile(
    org_urn: str,
    org_name: str,
    raw_batch_data: Dict[str, Any],
    company_profile_data: Optional[Dict[str, Any]] = None,
    follower_count: Optional[int] = None,
    posts_stored_count: int = 0,
    posts_analyzed_count: int = 0,
    total_posts_available: int = 0,
    last_post_urn: Optional[str] = None,
    last_post_published_at: Optional[str] = None,
    profile_hash: Optional[str] = None,
    followers_at_last_check: Optional[int] = None,
    change_reason: Optional[str] = None,
) -> str:
    """
    Persiste o actualiza el perfil enriquecido de empresa en BD mediante UPSERT atómico.

    :param org_urn: URN identificador único de LinkedIn.
    :param org_name: Nombre nominal extraído.
    :param raw_batch_data: Estructura JSON cruda de las APIs.
    :param company_profile_data: Perfil corporativo destilado vía LLM.
    :param follower_count: Total de audiencia actual.
    :param posts_stored_count: Posts ingestados localmente.
    :param posts_analyzed_count: Posts catalogados y analizados.
    :param total_posts_available: Volumen total detectado.
    :param last_post_urn: URN de la publicación más reciente.
    :param last_post_published_at: Timestamp de última publicación detectada.
    :param profile_hash: MD5 del perfil para control de derivas (change-detection).
    :param followers_at_last_check: Snapshot del volumen de audiencia previo.
    :param change_reason: Traza analítica del motivo de re-sincronización (ej: 'new_posts').
    :returns: ID relacional asignado al perfil corporativo (UUID string).
    """
    supabase = get_supabase()
    now = _dt.now(timezone.utc).isoformat()

    # Operación optimizada de lectura preventiva para retener Primary Key UUIDs previos.
    existing = get_company_profile(org_urn)
    record_id = existing["id"] if existing else str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "id": record_id,
        "org_urn": org_urn,
        "org_name": org_name,
        "raw_batch_data": raw_batch_data,
        "company_profile": company_profile_data,
        "follower_count": follower_count,
        "batch_extracted_at": now,
        "posts_stored_count": posts_stored_count,
        "posts_analyzed_count": posts_analyzed_count,
        "total_posts_available": total_posts_available,
        "last_post_urn": last_post_urn,
        "last_post_published_at": last_post_published_at,
        "profile_hash": profile_hash,
        "followers_at_last_check": followers_at_last_check,
        "last_change_check_at": now,
        "change_reason": change_reason,
        "updated_at": now,
    }

    # Filtrado selectivo de mutaciones parciales: purga atributos None
    # para prevenir destrucción de data en fases no completas de background tasks.
    payload = {k: v for k, v in payload.items() if v is not None}
    
    # Restitución de PKs críticas.
    payload["id"] = record_id
    payload["org_urn"] = org_urn
    payload["org_name"] = org_name

    if not existing:
        payload["created_at"] = now

    # Ejecución de UPSERT atómico tolerante a race conditions distribuidas.
    supabase.table("company_profiles").upsert(
        payload, on_conflict="org_urn"
    ).execute()
    logger.info(f"company_profile upserted para {org_urn} (id={record_id})")

    return record_id


def get_all_company_profiles() -> List[Dict[str, Any]]:
    """
    Recupera el listado íntegro de perfiles corporativos persistidos.

    :returns: Lista de diccionarios ordenados por fecha de última extracción (batch_extracted_at desc).
    """
    try:
        supabase = get_supabase()
        result = (
            supabase.table("company_profiles")
            .select("*")
            .order("batch_extracted_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Error listando company_profiles: {e}")
        return []


def get_latest_stored_snapshot(org_urn: str) -> Dict[str, Any]:
    """
    Recupera la captura temporal (snapshot) de métricas y content-hash para análisis de derivas.

    Utilizado por rutinas de detección de cambios (detect_company_changes) para resolver
    si el tenant requiere de un nuevo barrido integral de extracción.

    :param org_urn: Identificador de la cuenta de LinkedIn.
    :returns: Diccionario con last_post_urn, last_post_published_at, profile_hash y followers_at_last_check.
              Devuelve un diccionario base con valores None si el perfil no existe.
    """
    empty: Dict[str, Any] = {
        "last_post_urn": None,
        "last_post_published_at": None,
        "profile_hash": None,
        "followers_at_last_check": None,
    }
    try:
        supabase = get_supabase()
        result = (
            supabase.table("company_profiles")
            .select(
                "last_post_urn,"
                "last_post_published_at,"
                "profile_hash,"
                "followers_at_last_check"
            )
            .eq("org_urn", org_urn)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            return {
                "last_post_urn": row.get("last_post_urn"),
                "last_post_published_at": row.get("last_post_published_at"),
                "profile_hash": row.get("profile_hash"),
                "followers_at_last_check": row.get("followers_at_last_check"),
            }
        return empty
    except Exception as e:
        logger.error(f"Error fetching snapshot for {org_urn}: {e}")
        return empty


def save_engagement_insights(
    org_urn: str,
    engagement_insights: Dict[str, Any],
    top_performing_posts: List[Dict[str, Any]],
    engagement_analysis: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Centraliza el upsert de analíticas de rendimiento hacia la tabla engagement_insights
    y denormaliza los insights predictivos (LLM) en el registro maestro company_profiles.

    :param org_urn: URN corporativo base.
    :param engagement_insights: Agregados volumétricos y ratios consolidados.
    :param top_performing_posts: Listado del subconjunto de posts de mayor impacto.
    :param engagement_analysis: Opcional. Insight descriptivo generado por IA.
    :returns: UUID primario insertado, o None en caso de fallo.
    """
    try:
        supabase = get_supabase()
        now = _dt.now(timezone.utc).isoformat()

        aggregate = engagement_insights.get("aggregate_metrics", {})

        payload: Dict[str, Any] = {
            "org_urn": org_urn,
            "share_statistics": engagement_insights.get("share_statistics"),
            "page_statistics": engagement_insights.get("page_statistics"),
            "follower_statistics": engagement_insights.get("follower_statistics"),
            "top_performing_posts": top_performing_posts,
            "avg_engagement_rate": aggregate.get("avg_engagement_rate"),
            "total_impressions": aggregate.get("total_impressions", 0),
            "total_engagements": aggregate.get("total_engagements", 0),
            "engagement_analysis": engagement_analysis,
            "extracted_at": engagement_insights.get("extracted_at", now),
            "updated_at": now,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        payload["org_urn"] = org_urn  

        result = (
            supabase.table("engagement_insights")
            .upsert(payload, on_conflict="org_urn")
            .execute()
        )
        record_id = result.data[0]["id"] if result.data else None

        if engagement_analysis:
            (
                supabase.table("company_profiles")
                .update({"engagement_insights": engagement_analysis})
                .eq("org_urn", org_urn)
                .execute()
            )

        logger.info(
            f"[engagement] Saved engagement insights for {org_urn} "
            f"(id={record_id}, posts={aggregate.get('post_count', 0)}, "
            f"avg_rate={aggregate.get('avg_engagement_rate', 0):.4f})"
        )
        return record_id

    except Exception as e:
        logger.error(f"Error saving engagement insights for {org_urn}: {e}", exc_info=True)
        return None


def get_engagement_insights(org_urn: str) -> Optional[Dict[str, Any]]:
    """
    Resuelve métricas de engagement cacheadas para una organización específica.

    :param org_urn: URN identificador del perfil.
    :returns: Diccionario enriquecido con estadísticos ponderados (rates, sumatorias), o None si no existen.
    """
    try:
        supabase = get_supabase()
        result = (
            supabase.table("engagement_insights")
            .select("*")
            .eq("org_urn", org_urn)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        share_stats = row.get("share_statistics") or []
        t_likes = t_comments = t_shares = t_clicks = 0
        for stat in share_stats:
            ts = stat.get("totalShareStatistics", {})
            t_likes += ts.get("likeCount", 0) or 0
            t_comments += ts.get("commentCount", 0) or 0
            t_shares += ts.get("shareCount", 0) or 0
            t_clicks += ts.get("clickCount", 0) or 0
        t_imp = row.get("total_impressions") or 0
        t_eng = row.get("total_engagements") or 0
        avg_rate = float(row.get("avg_engagement_rate") or 0)
        pc = len(share_stats)
        return {
            "total_impressions": t_imp,
            "total_engagements": t_eng,
            "avg_engagement_rate": avg_rate,
            "total_likes": t_likes,
            "total_comments": t_comments,
            "total_shares": t_shares,
            "total_clicks": t_clicks,
            "avg_impressions_per_post": round(t_imp / pc) if pc > 0 else 0,
            "post_count": pc,
            "top_performing_posts": row.get("top_performing_posts") or [],
            "extracted_at": row.get("extracted_at"),
        }
    except Exception as e:
        logger.error("Error obteniendo metricas de engagement para %s: %s", org_urn, e)
        return None


def get_posts_count_by_account(account_id: str) -> int:
    """
    Computa el volumen total de publicaciones asociadas a una cuenta en base de datos.

    :param account_id: UUID de referencia a la cuenta.
    :returns: Entero representando el count exacto devuelto por PostgreSQL.
    """
    try:
        supabase = get_supabase()
        result = (
            supabase.table("posts")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .execute()
        )
        return result.count or 0
    except Exception as e:
        logger.error("Error contando publicaciones para la cuenta %s: %s", account_id, e)
        return 0


def update_change_check_timestamp(
    org_urn: str,
    change_reason: Optional[str] = None,
) -> None:
    """
    Registra el timestamp de último escaneo (last_change_check_at) para sincronía del scheduler.

    Permite a la tarea de refresco en background (Celery) declarar completitud de revisión 
    incluso cuando el estado de la organización no haya variado (sin mutación de datos reales).

    :param org_urn: URN objetivo.
    :param change_reason: Opcional. Vector CSV con los motivos del trigger (ej: 'new_posts').
    :returns: None.
    """
    try:
        supabase = get_supabase()
        now = _dt.now(timezone.utc).isoformat()
        payload: Dict[str, Any] = {
            "last_change_check_at": now,
            "change_reason": change_reason,
        }
        (
            supabase.table("company_profiles")
            .update(payload)
            .eq("org_urn", org_urn)
            .execute()
        )
        logger.debug(
            f"[change_check] Timestamp updated for {org_urn} | reason={change_reason!r}"
        )
    except Exception as e:
        logger.error(f"Error updating change_check_at for {org_urn}: {e}")