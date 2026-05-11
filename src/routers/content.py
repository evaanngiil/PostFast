from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from src.core.logger import logger
from src.celery_app import celery_app
from src.tasks import publish_post_task, content_generation_task, resume_content_generation_task
from datetime import datetime, timezone

import uuid
from fastapi import APIRouter, Depends
from src.dependencies.graph import get_graph
from src.services.api_client import (
    create_post, get_all_posts, get_post_by_id, update_post, delete_post,
    get_company_profile, get_all_company_profiles, is_first_company_connection,
    get_engagement_insights, get_posts_count_by_account,
)
from src.tasks import company_batch_extraction_task


# Importación y resolución de dependencias de autenticación.
try:
     # Asumiendo que está en main.py en el directorio superior
     from src.dependencies.auth import get_current_session_data_from_token
except ImportError:
     # Stub de fallback para prevenir errores en tiempo de importación.
     logger.critical("No se pudo importar la dependencia get_current_session_data_from_token!")
     async def get_current_session_data_from_token(token: str | None = None):
          raise NotImplementedError("Dependencia de auth no cargada")

content_router = APIRouter()

# Modelos de validación Pydantic para payloads HTTP.
class SchedulePostPayload(BaseModel):
    platform: str
    account_id: str
    content: str
    scheduled_time_str: Optional[str] = None
    link_url: Optional[str] = None

class ContentGenerationPayload(BaseModel):
    query: str = Field(..., description="The main description of what to post.")
    tone: str = Field(..., description="The desired tone of the message (e.g., Professional, Funny).")
    niche: str = Field(..., description="The target audience or niche.")
    account_name: str = Field(..., description="The name of the account publishing the content.")
    link_url: Optional[str] = Field(None, description="An optional URL to include or summarize.")
    selected_account: Dict[str, Any] = Field(..., description="The selected LinkedIn account/organization object from the session.")


class ResumePayload(BaseModel):
    task_id: str
    feedback: str # El feedback del usuario. Puede ser "aprobar" o un texto.

class PostCreatePayload(BaseModel):
    content: str
    status: str
    platform: str
    account_id: str
    scheduled_time: Optional[datetime] = None
    published_time: Optional[datetime] = None
    title: Optional[str] = None
    feedback: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None

class PostUpdatePayload(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    published_time: Optional[datetime] = None
    title: Optional[str] = None
    feedback: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None

class SaveForLaterPayload(BaseModel):
    content: str
    platform: str
    account_id: str
    title: Optional[str] = None
    feedback: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None


@content_router.post("/schedule_post")
async def schedule_post_endpoint(
    payload: SchedulePostPayload,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Controlador para programar o publicar inmediatamente un post vía Celery.

    :param payload: Payload Pydantic con detalles de publicación.
    :param session_data: Dependencia inyectada con datos de sesión validados.
    :returns: Diccionario con task_id y un mensaje de estado.
    """
    user_info = session_data.get("user_info", {})
    user_token_data = session_data.get("token_data", {})
    user_access_token = user_token_data.get("access_token")
    session_provider = session_data.get("provider")

    logger.info(f"Recibida peticion para programar post en plataforma {payload.platform}, Cuenta: {payload.account_id} por el usuario {user_info.get('id', 'N/A')}")

    if not user_access_token:
        raise HTTPException(status_code=401, detail="Falta el token de acceso del usuario en los datos de sesion.")
    if session_provider and payload.platform.lower() != session_provider.lower():
         logger.warning(f"La plataforma del payload ({payload.platform}) no coincide con el proveedor de la sesion ({session_provider}).")

    token_for_api = user_access_token

    task_args = [
        payload.platform,
        payload.account_id,
        token_for_api,
        payload.content
    ]

    task_kwargs = {
        "link_url": payload.link_url
    }
    
    task_kwargs = {k: v for k, v in task_kwargs.items() if v is not None}

    try:
        if payload.scheduled_time_str:
            try: 
                scheduled_dt = datetime.fromisoformat(payload.scheduled_time_str.replace('Z', '+00:00'))
            except ValueError: 
                scheduled_dt_naive = datetime.fromisoformat(payload.scheduled_time_str) 
                scheduled_dt = scheduled_dt_naive.replace(tzinfo=timezone.utc)

            if scheduled_dt <= datetime.now(timezone.utc):
                 logger.warning(f"El tiempo programado {payload.scheduled_time_str} esta en el pasado. Publicando ahora.")
                 task = publish_post_task.delay(*task_args, **task_kwargs)
                 msg = "El tiempo programado esta en el pasado, la tarea de publicacion comenzo ahora."
                 # Persistencia en BD de registro en estado publicado.
                 create_post(
                     content=payload.content,
                     status="published",
                     platform=payload.platform,
                     account_id=payload.account_id,
                     published_time=datetime.now(timezone.utc),
                     scheduled_time=scheduled_dt,
                     link_url=payload.link_url
                 )
            else:
                task = publish_post_task.apply_async(args=task_args, kwargs=task_kwargs, eta=scheduled_dt)
                msg = f"Post programado con exito para {scheduled_dt.isoformat()}."
                logger.info(f"Tarea de programacion de post creada. Task ID: {task.id}, ETA: {scheduled_dt}")
                # Persistencia en BD de registro en estado programado.
                create_post(
                    content=payload.content,
                    status="scheduled",
                    platform=payload.platform,
                    account_id=payload.account_id,
                    scheduled_time=scheduled_dt,
                    link_url=payload.link_url
                )
        else: # Ejecución asíncrona inmediata.
            task = publish_post_task.delay(*task_args, **task_kwargs)
            msg = "La tarea de publicacion de post comenzo ahora."
            logger.info(f"Tarea de publicacion de post lanzada inmediatamente. Task ID: {task.id}")
            # Persistencia sincrónica en BD post-dispatch.
            create_post(
                content=payload.content,
                status="published",
                platform=payload.platform,
                account_id=payload.account_id,
                published_time=datetime.now(timezone.utc),
                link_url=payload.link_url
            )

        return {"task_id": task.id, "message": msg}

    except ValueError as ve:
         logger.error(f"Formato de tiempo programado invalido: {payload.scheduled_time_str}. Error: {ve}")
         raise HTTPException(status_code=400, detail=f"Formato de tiempo programado invalido: {payload.scheduled_time_str}. Utiliza formato ISO 8601.")
    except Exception as e:
        logger.exception("Fallo al programar la tarea del post")
        raise HTTPException(status_code=500, detail="Fallo al programar la tarea del post")


@content_router.post(
    "/generate_post", 
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_post_start(
    payload: ContentGenerationPayload,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Encola una tarea de generación de contenido (draft inicial) en el grafo de Celery.

    :param payload: Modelo Pydantic con la configuración del contenido.
    :param session_data: Dependencia de sesión actual.
    :returns: Diccionario con el ID de la tarea encolada.
    """
    user_info = session_data.get("user_info", {})
    payload_dict = payload.model_dump()

    # Inyectar explícitamente el token de acceso OAuth en el payload 
    # dado que el worker de Celery no comparte contexto con FastAPI.
    user_token_data = session_data.get("token_data", {})
    payload_dict["access_token"] = user_token_data.get("access_token", "")

    # Invocación asíncrona; .delay() retorna el descriptor AsyncResult.
    logger.warning(f"[AI LangGraph] Encolando tarea para  {payload_dict}")
    task = content_generation_task.delay(payload_dict=payload_dict)

    logger.info(f"El usuario {user_info.get('id', 'N/A')} ha encolado la tarea {task.id}.")

    return {"task_id": task.id}

@content_router.get("/generate_post/status/{task_id}")
async def get_generation_status(task_id: str):
    """
    Consulta activamente el Result Backend (Redis) para determinar el estado de una tarea asíncrona.

    :param task_id: Identificador único de la tarea Celery.
    :returns: Estado actual y resultados/errores embebidos si existen.
    """
    task_result = celery_app.AsyncResult(task_id)

    if task_result.state == 'PENDING':
        # Tarea encolada, esperando worker disponible o en ejecución inicial.
        return {"status": "PENDING"}
    elif task_result.state == 'SUCCESS':
        # Tarea finalizada con éxito; result contiene el payload computado.
        return {"status": "SUCCESS", "result": task_result.result}
    elif task_result.state == 'FAILURE':
        # Tarea abortada; result expone el traceback o mensaje de excepción.
        return {"status": "FAILURE", "error": str(task_result.result)}
    elif task_result.state == 'PENDING_USER_INPUT':
        # Tarea pausada; el grafo requiere validación humana (Human-in-the-loop).
        return {
            "status": "PENDING_USER_INPUT", 
            "info": task_result.info,
            "draft_content": task_result.info.get('draft_content') if task_result.info else None
        }
    else:
        return {"status": task_result.state, "info": task_result.info}


@content_router.post("/generate_post/resume", status_code=status.HTTP_202_ACCEPTED)
async def generate_post_resume(
    payload: ResumePayload,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Despierta una tarea de generación previamente suspendida y le inyecta el feedback del usuario.

    :param payload: Payload que contiene el task_id previo y el texto de feedback.
    :param session_data: Estado de sesión validado.
    :returns: Nuevo ID de tarea para trackear la reanudación.
    """
    # 1. Validación de estado en el broker.
    original_task_result = celery_app.AsyncResult(payload.task_id)
    if original_task_result.state != 'PENDING_USER_INPUT':
        raise HTTPException(status_code=400, detail="La tarea no esta pendiente de la entrada del usuario.")

    checkpoint = original_task_result.info.get('checkpoint')
    if not checkpoint:
        raise HTTPException(status_code=404, detail="No se encontro checkpoint para la tarea.")

    # 3. Encolar la continuación del grafo inyectando estado y nuevos inputs.
    resume_task = resume_content_generation_task.delay(
        checkpoint=checkpoint,
        payload=payload.model_dump()
    )

    logger.info(f"Reanudando la tarea {payload.task_id} con el feedback del usuario. Nuevo task ID: {resume_task.id}")
    return {"task_id": resume_task.id, "message": "Tarea de generacion de contenido reanudada."}

@content_router.post("/posts", response_model=str)
async def create_post_endpoint(payload: PostCreatePayload, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Crea un nuevo registro de post en la base de datos.

    :param payload: Modelo Pydantic con los datos del post.
    :param session_data: Sesión del usuario inyectada.
    :returns: Identificador UUID del post creado.
    """
    post_id = create_post(**payload.model_dump())
    return post_id

@content_router.get("/posts", response_model=List[Dict[str, Any]])
async def list_posts_endpoint(status: Optional[str] = None, account_id: Optional[str] = None, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Lista los posts creados por el usuario, filtrables por status o account_id.

    :param status: Opcional. Filtro por estado (ej. 'published', 'scheduled').
    :param account_id: Opcional. Filtro por cuenta asociada.
    :param session_data: Sesión del usuario inyectada.
    :returns: Lista de diccionarios con la metadata de cada post.
    """
    return get_all_posts(status=status, account_id=account_id)

@content_router.get("/posts/{post_id}", response_model=Dict[str, Any])
async def get_post_endpoint(post_id: str, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Recupera un post específico según su ID.

    :param post_id: Identificador único del post.
    :param session_data: Sesión del usuario inyectada.
    :returns: Diccionario con la información del post.
    :raises HTTPException: Si el post no es encontrado (404).
    """
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    return post

@content_router.put("/posts/{post_id}", response_model=bool)
async def update_post_endpoint(post_id: str, payload: PostUpdatePayload, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Actualiza parcialmente un registro de post existente.

    :param post_id: Identificador único del post.
    :param payload: Modelo Pydantic con los campos a modificar.
    :param session_data: Sesión del usuario inyectada.
    :returns: True si la actualización fue exitosa.
    :raises HTTPException: Si no se proveen campos para actualizar (400).
    """
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    return update_post(post_id, updates)

@content_router.delete("/posts/{post_id}", response_model=bool)
async def delete_post_endpoint(post_id: str, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Elimina físicamente o lógicamente un post de la base de datos.

    :param post_id: Identificador único del post a eliminar.
    :param session_data: Sesión del usuario inyectada.
    :returns: True si la eliminación fue exitosa.
    """
    return delete_post(post_id)

@content_router.post("/save_for_later", response_model=str)
async def save_for_later_endpoint(
    payload: SaveForLaterPayload,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Registra un post en la base de datos marcándolo como borrador/guardado para después.

    :param payload: Datos del post a guardar.
    :param session_data: Sesión del usuario.
    :returns: String con el ID del post creado.
    """
    user_info = session_data.get("user_info", {})
    logger.info(f"El usuario {user_info.get('id', 'N/A')} esta guardando el post para mas tarde en {payload.platform}")
    
    try:
        post_id = create_post(
            content=payload.content,
            status="saved_for_later",
            platform=payload.platform,
            account_id=payload.account_id,
            title=payload.title,
            feedback=payload.feedback,
            image_url=payload.image_url,
            link_url=payload.link_url
        )
        return post_id
    except Exception as e:
        logger.exception("Fallo al guardar el post para mas tarde")
        raise HTTPException(status_code=500, detail="Fallo al guardar el post para mas tarde")


# Endpoints de Perfiles de Empresa (Company Profiles).

class CompanyBatchTriggerPayload(BaseModel):
    org_urn: str = Field(..., description="URN de la organizacion (ej. 'urn:li:organization:12345').")
    org_name: str = Field(..., description="Nombre legible de la organizacion.")


@content_router.get(
    "/company/profiles",
    response_model=List[Dict[str, Any]],
    summary="Lista todos los perfiles de empresa extraidos",
    tags=["Company Profiles"],
)
async def list_company_profiles_endpoint(
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Recupera el catálogo completo de perfiles de empresa cacheados en la base de datos.

    :param session_data: Dependencia inyectada con la sesión activa.
    :returns: Lista de diccionarios con la metadata extraída de cada empresa.
    """
    try:
        return get_all_company_profiles()
    except Exception as e:
        logger.exception("Error listando company_profiles")
        raise HTTPException(status_code=500, detail="Error recuperando perfiles de empresa")


@content_router.get(
    "/company/profiles/{org_urn:path}",
    response_model=Dict[str, Any],
    summary="Obtiene el perfil de empresa para un URN especifico",
    tags=["Company Profiles"],
)
async def get_company_profile_endpoint(
    org_urn: str,
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Recupera el perfil específico y enriquecido de una organización basada en su URN.

    :param org_urn: URN de la organización en LinkedIn.
    :param session_data: Sesión autenticada.
    :returns: Diccionario con la metadata o 404 si la tarea batch no ha concluido.
    """
    profile = get_company_profile(org_urn)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontro perfil de empresa para el URN: {org_urn}. "
                   "Puede que la extraccion batch aun no haya terminado.",
        )
    return profile


@content_router.post(
    "/company/profiles/trigger_batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispara manualmente la extraccion batch de una empresa",
    tags=["Company Profiles"],
)
async def trigger_company_batch_endpoint(
    payload: CompanyBatchTriggerPayload,
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Punto de entrada manual para forzar la tarea ETL de extracción de empresa.

    :param payload: Datos de la organización a extraer.
    :param session_data: Sesión del usuario actual.
    :returns: Diccionario con ID de tarea e información de estado.
    """
    user_token_data = session_data.get("token_data", {})
    access_token = user_token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Token de acceso no disponible en la sesion.")

    try:
        task = company_batch_extraction_task.delay(
            org_urn=payload.org_urn,
            org_name=payload.org_name,
            access_token=access_token,
        )
        logger.info(
            f"Tarea company_batch_extraction_task encolada manualmente. "
            f"Task ID: {task.id} para {payload.org_urn}"
        )
        return {
            "task_id": task.id,
            "message": f"Extraccion batch iniciada para '{payload.org_name}' ({payload.org_urn}).",
        }
    except Exception as e:
        logger.exception("Error al encolar company_batch_extraction_task manualmente")
        raise HTTPException(status_code=500, detail="No se pudo encolar la tarea de extraccion batch.")

# Sistema de detección de cambios y refresco.
class CheckUpdatesPayload(BaseModel):
    org_urn: str = Field(..., description="LinkedIn organization URN, e.g. 'urn:li:organization:12345'")
    org_name: str = Field(..., description="Human-readable organization name (used in logs and task result).")


@content_router.post("/company/profiles/check_updates")
async def check_company_updates_endpoint(
    payload: CheckUpdatesPayload,
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Encola una tarea de refresco (company_batch_refresh_task) evaluando políticas de cooldown.

    :param payload: URN y nombre de la empresa.
    :param session_data: Sesión inyectada.
    :returns: Diccionario con task_id y mensaje estructurado.
    """
    from src.tasks import company_batch_refresh_task

    user_token_data = session_data.get("token_data", {})
    access_token = user_token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de acceso de LinkedIn en los datos de la sesion.",
        )

    # Deduplicación activa: previene saturación del broker y agotamiento de quota 
    # de API si múltiples requests de refresco ocurren en un margen corto de tiempo.
    COOLDOWN_SECONDS = 300  # 5 minutos entre checks de refresco por org

    try:
        existing = get_company_profile(payload.org_urn)
        if existing:
            last_check_str = existing.get("last_change_check_at")
            if last_check_str:
                from datetime import datetime, timezone
                # Handle both ISO format strings and datetime objects
                if isinstance(last_check_str, str):
                    last_check = datetime.fromisoformat(last_check_str.replace("Z", "+00:00"))
                else:
                    last_check = last_check_str
                elapsed = (datetime.now(timezone.utc) - last_check).total_seconds()
                if elapsed < COOLDOWN_SECONDS:
                    logger.info(
                        f"[check_updates] Omitiendo refresco para '{payload.org_name}' "
                        f"({payload.org_urn}) — ultimo check hace {elapsed:.0f}s "
                        f"(cooldown={COOLDOWN_SECONDS}s)"
                    )
                    return {
                        "task_id": None,
                        "status": "skipped",
                        "message": (
                            f"Refresco omitido para '{payload.org_name}': "
                            f"ultimo check fue hace {elapsed:.0f}s."
                        ),
                    }
    except Exception as dedup_exc:
        # Fallback de seguridad: si el check de cooldown falla, permitir ejecución.
        logger.warning(f"[check_updates] Dedup check failed for {payload.org_urn}: {dedup_exc}")

    logger.info(
        f"[check_updates] Encolando refresco para '{payload.org_name}' ({payload.org_urn})"
    )

    try:
        task = company_batch_refresh_task.delay(
            org_urn=payload.org_urn,
            org_name=payload.org_name,
            access_token=access_token,
        )
        logger.info(f"[check_updates] Tarea encolada: task_id={task.id} para {payload.org_urn}")
        return {
            "task_id": task.id,
            "status": "enqueued",
            "message": f"Tarea de refresco encolada para '{payload.org_name}'.",
        }
    except Exception as exc:
        logger.exception(f"[check_updates] Fallo al encolar la tarea de refresco para {payload.org_urn}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fallo al encolar la tarea de refresco de la empresa.",
        )


# Endpoints de métricas y analíticas (Engagement).

@content_router.get(
    "/engagement/{org_urn:path}",
    response_model=Dict[str, Any],
    summary="Obtener metricas de engagement para una organizacion",
)
async def get_engagement_endpoint(
    org_urn: str,
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Calcula y devuelve métricas agregadas de rendimiento (impresiones, likes, etc.) para una organización.

    :param org_urn: URN de la entidad.
    :param session_data: Datos de sesión inyectados.
    :returns: Diccionario con estadísticas computadas.
    """
    insights = get_engagement_insights(org_urn)
    if not insights:
        return {
            "total_impressions": 0,
            "total_engagements": 0,
            "avg_engagement_rate": 0.0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "total_clicks": 0,
            "avg_impressions_per_post": 0,
            "post_count": 0,
            "top_performing_posts": [],
            "extracted_at": None,
        }
    return insights


@content_router.get(
    "/posts/count",
    response_model=Dict[str, int],
    summary="Obtener el conteo total de posts para una cuenta",
)
async def get_posts_count_endpoint(
    account_id: str,
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Agregación rápida: cuenta el total de posts históricos asociados a un account_id.

    :param account_id: Identificador de la cuenta de plataforma.
    :param session_data: Sesión validada.
    :returns: Diccionario con el conteo entero.
    """
    count = get_posts_count_by_account(account_id)
    return {"count": count}
