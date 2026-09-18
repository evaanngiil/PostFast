"""
Capa de acceso a datos (DTO) sobre Supabase para el backend.

NOTA: Los antiguos helpers HTTP (`get_api_client`, `start_content_generation`,
`schedule_or_publish_post`, `resume_content_generation`, etc.) que la UI de
Streamlit usaba para hablar con FastAPI se han retirado junto con el frontend
Streamlit. El backend (tareas Celery, routers y nodos del grafo) accede a la
base de datos directamente a través de las funciones DTO de este módulo.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime as _dt, timezone
import uuid

from src.core.logger import logger
from src.services.supabase_client import get_supabase_admin as get_supabase


# Controladores DTO para Gestión de Publicaciones.
def create_post(
    content: str,
    status: str,
    platform: str,
    account_id: str,
    scheduled_time: Optional[_dt] = None,
    published_time: Optional[_dt] = None,
    title: Optional[str] = None,
    feedback: Optional[str] = None,
    image_url: Optional[str] = None,
    link_url: Optional[str] = None,
    post_id: Optional[str] = None,
    score: Optional[int] = None
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
    :param post_id: Opcional UUID pre-generado para alinear con el thread_id de LangGraph.
    :param score: Opcional puntuación de calidad (0 a 100).
    :returns: ID insertado (UUID string).
    """
    supabase = get_supabase()
    id_to_use = post_id if post_id else str(uuid.uuid4())

    if score is None and content:
        try:
            from src.services.rag_service import evaluate_post_quality
            score = evaluate_post_quality(content)
        except Exception as e:
            logger.warning(f"Error autoevaluando score en create_post: {e}")

    # Serialización explícita a ISO format para evitar errores de JSON en Supabase
    s_time = scheduled_time.isoformat() if scheduled_time else None
    p_time = published_time.isoformat() if published_time else None

    payload = {
        "id": id_to_use,
        "content": content,
        "status": status,
        "platform": platform,
        "account_id": account_id,
        "scheduled_time": s_time,
        "published_time": p_time,
        "title": title,
        "feedback": feedback,
        "image_url": image_url,
        "link_url": link_url,
        "score": score,
    }

    try:
        supabase.table("posts").insert({k: v for k, v in payload.items() if v is not None}).execute()
        return id_to_use
    except Exception as e:
        logger.error(f"Error persistiendo post en DB: {e}")
        raise # Re-lanzar para que el router sepa que falló

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
    posts = result.data or []

    # Evaluar score para posts que no lo tengan
    for post in posts:
        if post.get("score") is None and post.get("content"):
            try:
                from src.services.rag_service import evaluate_post_quality
                post_score = evaluate_post_quality(post["content"])
                post["score"] = post_score
                update_post(post["id"], {"score": post_score})
            except Exception as e:
                logger.warning(f"Error autoevaluando post histórico {post['id']}: {e}")

    return posts

def get_post_by_id(post_id: str) -> Optional[Dict[str, Any]]:
    """
    Búsqueda individual mediante Primary Key UUID.

    NOTA: no usar .single() aquí — PostgREST lanza PGRST116 ("Cannot coerce the
    result to a single JSON object") cuando hay 0 filas, en lugar de devolver
    None. Esto ocurre legítimamente cuando el frontend envía un post_id
    pre-generado (alineado al thread de LangGraph) que aún no se ha insertado.

    :param post_id: Cadena identificadora.
    :returns: Documento consolidado del post, o None si no hace hit.
    """
    supabase = get_supabase()
    result = supabase.table("posts").select("*").eq("id", post_id).limit(1).execute()
    post = result.data[0] if result.data else None
    if post and post.get("score") is None and post.get("content"):
        try:
            from src.services.rag_service import evaluate_post_quality
            post_score = evaluate_post_quality(post["content"])
            post["score"] = post_score
            update_post(post_id, {"score": post_score})
        except Exception as e:
            logger.warning(f"Error autoevaluando post individual {post_id}: {e}")
    return post

def update_post(post_id: str, updates: Dict[str, Any]) -> bool:
    """
    Actualización idempotente mediante partial payload para registro específico.

    :param post_id: Puntero de referencia primaria.
    :param updates: Diccionario que abstrae a un objeto Pydantic UpdatePayload filtrado.
    :returns: True si se logró la operación atómica de mutación local.
    """
    if not updates:
        return False

    # Si cambia el contenido y no se provee score, reevaluar calidad
    if "content" in updates and updates["content"] and "score" not in updates:
        try:
            from src.services.rag_service import evaluate_post_quality
            updates["score"] = evaluate_post_quality(updates["content"])
        except Exception as e:
            logger.warning(f"Error autoevaluando score en update_post para {post_id}: {e}")

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
        
        # Query actual analyzed/stored post count from company_profiles
        actual_post_count = 0
        try:
            profile_res = (
                supabase.table("company_profiles")
                .select("posts_analyzed_count, posts_stored_count")
                .eq("org_urn", org_urn)
                .limit(1)
                .execute()
            )
            if profile_res.data:
                profile_row = profile_res.data[0]
                actual_post_count = profile_row.get("posts_analyzed_count") or profile_row.get("posts_stored_count") or 0
        except Exception as p_err:
            logger.debug(f"Could not resolve actual post count for {org_urn}: {p_err}")
            
        pc = actual_post_count if actual_post_count > 0 else len(share_stats)
        
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
            "aggregate_metrics": {
                "avg_engagement_rate": avg_rate,
                "total_impressions": t_imp,
                "total_engagements": t_eng,
                "post_count": pc,
            },
            "engagement_analysis": row.get("engagement_analysis")
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


# --- CRUD Skills ---

def create_skill(org_urn: str, name: str, description: Optional[str], markdown_content: str) -> Optional[str]:
    try:
        supabase = get_supabase()
        payload = {
            "org_urn": org_urn,
            "name": name,
            "description": description,
            "markdown_content": markdown_content
        }
        result = supabase.table("skills").insert(payload).execute()
        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        logger.error(f"Error creating skill for {org_urn}: {e}")
        return None

def get_all_skills(org_urn: str) -> List[Dict[str, Any]]:
    try:
        supabase = get_supabase()
        result = supabase.table("skills").select("*").eq("org_urn", org_urn).order("created_at", desc=False).execute()
        skills = result.data or []
        
        # Check if Base Skill exists
        base_name = "Guía de Estilo y Generación (Base)"
        base_skill = next((s for s in skills if s.get("name") == base_name), None)
        
        if not base_skill and org_urn and not org_urn.startswith("urn:li:person:"):
            # Create default Base Skill
            default_markdown = """# Guía de Estilo y Generación (Base)

Esta es la directriz base utilizada por el agente de Inteligencia Artificial para la redacción de publicaciones en LinkedIn. Puedes editar esta guía para personalizar el estilo general de tu cuenta.

## 1. Voz de la Marca y Tono
- **Profesional pero Cercano:** Hablar de tecnología, negocios e innovación de forma de forma directa y cercana.
- **Empático y Orientado a Soluciones:** Enfocarse en resolver desafíos reales de la audiencia.
- **Evitar Argot Excesivo:** Explicar términos complejos cuando sea necesario.

## 2. Pautas de Redacción
- **Gancho Inicial (Hook):** La primera línea debe captar la atención de inmediato con una pregunta intrigante, un dato impactante o una afirmación provocativa.
- **Estructura Legible:** Utilizar párrafos cortos (de 2 a 3 líneas máximo) y saltos de línea frecuentes para facilitar la lectura móvil.
- **Bullet Points:** Usar viñetas o emojis selectivos para estructurar listas de datos o beneficios clave.

## 3. Palabras Clave y Temas de Interés
- **Palabras Clave Preferidas:** Innovación, Eficiencia, Sostenibilidad, Transformación Digital, Liderazgo.
- **Temas Clave:** Casos de éxito, lecciones aprendidas, tendencias del mercado, consejos prácticos.

## 4. Estructura del Cierre
- **Llamada a la Acción (CTA):** Finalizar con una pregunta abierta para fomentar comentarios o invitar a leer más en el enlace oficial.
- **Hashtags:** Agregar de 3 a 5 hashtags específicos del sector al final del texto."""
            
            payload = {
                "org_urn": org_urn,
                "name": base_name,
                "description": "Directrices base obligatorias de tono de voz, estructura y formato del post.",
                "markdown_content": default_markdown
            }
            res_insert = supabase.table("skills").insert(payload).execute()
            if res_insert.data:
                skills.insert(0, res_insert.data[0])
                
        return skills
    except Exception as e:
        logger.error(f"Error getting skills for {org_urn}: {e}")
        return []

def get_skill_by_id(skill_id: str) -> Optional[Dict[str, Any]]:
    try:
        supabase = get_supabase()
        result = supabase.table("skills").select("*").eq("id", skill_id).single().execute()
        return result.data if result.data else None
    except Exception as e:
        logger.error(f"Error getting skill {skill_id}: {e}")
        return None

def update_skill(skill_id: str, updates: Dict[str, Any]) -> bool:
    try:
        supabase = get_supabase()
        updates["updated_at"] = _dt.now(timezone.utc).isoformat()
        result = supabase.table("skills").update(updates).eq("id", skill_id).execute()
        return bool(result.data)
    except Exception as e:
        logger.error(f"Error updating skill {skill_id}: {e}")
        return False

def delete_skill(skill_id: str) -> bool:
    try:
        supabase = get_supabase()
        result = supabase.table("skills").delete().eq("id", skill_id).execute()
        return bool(result.data)
    except Exception as e:
        logger.error(f"Error deleting skill {skill_id}: {e}")
        return False