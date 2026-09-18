from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from src.core.logger import logger
from src.celery_app import celery_app
from src.tasks import publish_post_task, content_generation_task, resume_content_generation_task
from datetime import datetime, timezone

import io
import pypdf
from fastapi import UploadFile, File
from src.services.api_client import (
    create_post, get_all_posts, get_post_by_id, update_post, delete_post,
    get_company_profile, get_all_company_profiles, get_engagement_insights, get_posts_count_by_account,
    create_skill, get_all_skills, get_skill_by_id, update_skill, delete_skill
)
from src.tasks import company_batch_extraction_task
from src.dependencies.org_access import (
    assert_org_access,
    register_org_access,
    get_user_org_urns,
)


# Importación y resolución de dependencias de autenticación.
try:
     # Asumiendo que está en main.py en el directorio superior
     from src.dependencies.auth import get_current_session_data_from_token, oauth2_scheme
     
     def get_current_session_data_from_token_or_query(
         token: Optional[str] = None,
         auth_token: Optional[str] = Depends(oauth2_scheme)
     ) -> dict:
         actual_token = token or auth_token
         return get_current_session_data_from_token(actual_token)
except ImportError:
     # Stub de fallback para prevenir errores en tiempo de importación.
     logger.critical("No se pudo importar la dependencia get_current_session_data_from_token!")
     async def get_current_session_data_from_token(token: str | None = None):
          raise NotImplementedError("Dependencia de auth no cargada")
          
     async def get_current_session_data_from_token_or_query(token: str | None = None):
          raise NotImplementedError("Dependencia de auth no cargada")

content_router = APIRouter()

def remove_overlap(s1: str, s2: str) -> str:
    s1_clean = s1.rstrip()
    s2_clean = s2.lstrip()
    max_overlap = min(len(s1_clean), len(s2_clean), 250)
    for size in range(max_overlap, 0, -1):
        if s1_clean.endswith(s2_clean[:size]):
            match_index = len(s1_clean) - size
            return s1[:match_index] + s2_clean
    return s1 + "\n\n" + s2

# Modelos de validación Pydantic para payloads HTTP.
class SchedulePostPayload(BaseModel):
    platform: str
    account_id: str
    content: str
    scheduled_time_str: Optional[str] = None
    link_url: Optional[str] = None
    post_id: Optional[str] = None
    thread_id: Optional[str] = None

class SkillCreatePayload(BaseModel):
    org_urn: str
    name: str
    description: Optional[str] = None
    markdown_content: str

class SkillUpdatePayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    markdown_content: Optional[str] = None

class ContentGenerationPayload(BaseModel):
    query: str = Field(..., description="The main description of what to post.")
    tone: Optional[str] = Field("Profesional", description="The desired tone of the message (e.g., Professional, Funny).")
    # Deprecado: el público objetivo se infiere de la petición del usuario. Se
    # mantiene opcional por compatibilidad con clientes antiguos.
    niche: Optional[str] = Field(None, description="(Deprecado) Público objetivo/nicho; se infiere del input del usuario.")
    account_name: str = Field(..., description="The name of the account publishing the content.")
    link_url: Optional[str] = Field(None, description="An optional URL to include or summarize.")
    selected_account: Dict[str, Any] = Field(..., description="The selected LinkedIn account/organization object from the session.")
    skill_id: Optional[str] = Field(None, description="Optional skill ID to inject markdown context into the generator.")
    selected_skills: Optional[List[str]] = Field(default_factory=list, description="Optional list of skill IDs to inject markdown context into the generator.")
    thread_id: Optional[str] = Field(None, description="Optional thread ID to resume a previous conversation context.")
    edit_mode: Optional[bool] = Field(False, description="Whether we are editing an existing post")
    # Modo edición estructurado (sustituye al protocolo de string mágico embebido en 'query').
    original_post: Optional[str] = Field(None, description="Texto original del post a editar (modo edición).")
    edit_instructions: Optional[str] = Field(None, description="Instrucciones de mejora del usuario (modo edición).")


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
    user_access_token = session_data.get("linkedin_access_token") or user_token_data.get("access_token")
    session_provider = session_data.get("provider")

    logger.info(f"Recibida peticion para programar post en plataforma {payload.platform}, Cuenta: {payload.account_id} por el usuario {user_info.get('id', 'N/A')}")

    if not user_access_token:
        raise HTTPException(status_code=401, detail="Falta el token de acceso del usuario en los datos de sesion.")
    if session_provider and session_provider.lower() != 'supabase' and payload.platform.lower() != session_provider.lower():
         logger.warning(f"La plataforma del payload ({payload.platform}) no coincide con el proveedor de la sesion ({session_provider}).")

    # El usuario publica con su propio token OAuth sobre esta cuenta: registrar vínculo tenant.
    register_org_access(session_data, payload.account_id)

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

    def save_or_update_post(status: str, scheduled_time=None, published_time=None):
        if payload.post_id:
            existing = get_post_by_id(payload.post_id)
            if existing:
                s_time = scheduled_time.isoformat() if scheduled_time else None
                p_time = published_time.isoformat() if published_time else None
                update_post(payload.post_id, {
                    "content": payload.content,
                    "status": status,
                    "platform": payload.platform,
                    "account_id": payload.account_id,
                    "scheduled_time": s_time,
                    "published_time": p_time,
                    "link_url": payload.link_url
                })
                return payload.post_id
            else:
                return create_post(
                    content=payload.content,
                    status=status,
                    platform=payload.platform,
                    account_id=payload.account_id,
                    scheduled_time=scheduled_time,
                    published_time=published_time,
                    link_url=payload.link_url,
                    post_id=payload.post_id
                )
        else:
            return create_post(
                content=payload.content,
                status=status,
                platform=payload.platform,
                account_id=payload.account_id,
                scheduled_time=scheduled_time,
                published_time=published_time,
                link_url=payload.link_url
            )

    try:
        scheduled_dt = None
        if payload.scheduled_time_str:
            try: 
                scheduled_dt = datetime.fromisoformat(payload.scheduled_time_str.replace('Z', '+00:00'))
            except ValueError: 
                scheduled_dt_naive = datetime.fromisoformat(payload.scheduled_time_str) 
                scheduled_dt = scheduled_dt_naive.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if scheduled_dt and scheduled_dt > now:
            initial_status = "scheduled"
            published_time = None
        else:
            initial_status = "published"
            published_time = now
            if scheduled_dt and scheduled_dt <= now:
                 logger.warning(f"El tiempo programado {payload.scheduled_time_str} esta en el pasado. Publicando ahora.")

        post_id = save_or_update_post(
            status=initial_status,
            scheduled_time=scheduled_dt,
            published_time=published_time
        )

        # Index approved post in RAG company_knowledge
        try:
            from src.services.rag_service import index_and_manage_reference_posts
            index_and_manage_reference_posts(
                org_urn=payload.account_id,
                post_id=post_id,
                content=payload.content,
                metadata={"post_id": post_id, "status": initial_status}
            )
            logger.info(f"Post {post_id} indexed and managed in reference queue successfully.")
        except Exception as err:
            logger.warning(f"Failed to index post {post_id} in RAG: {err}")

        task_kwargs["post_id"] = post_id

        if scheduled_dt and scheduled_dt > now:
            task = publish_post_task.apply_async(args=task_args, kwargs=task_kwargs, eta=scheduled_dt)
            msg = f"Post programado con exito para {scheduled_dt.isoformat()}."
            logger.info(f"Tarea de programacion de post creada. Task ID: {task.id}, ETA: {scheduled_dt}")
        else:
            task = publish_post_task.delay(*task_args, **task_kwargs)
            msg = "La tarea de publicacion de post comenzo ahora."
            logger.info(f"Tarea de publicacion de post lanzada inmediatamente. Task ID: {task.id}")

        return {"task_id": task.id, "message": msg}
    except ValueError as ve:
         logger.error(f"Formato de tiempo programado invalido: {payload.scheduled_time_str}. Error: {ve}")
         raise HTTPException(status_code=400, detail=f"Formato de tiempo programado invalido: {payload.scheduled_time_str}. Utiliza formato ISO 8601.")
    except Exception:
        logger.exception("Fallo al programar la tarea del post")
        raise HTTPException(status_code=500, detail="Fallo al programar la tarea del post")


@content_router.post("/save_draft")
async def save_draft_endpoint(
    payload: SchedulePostPayload,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Controlador para guardar un post como borrador sin publicarlo ni programarlo.
    """
    user_info = session_data.get("user_info", {})
    logger.info(f"Recibida peticion para guardar borrador en plataforma {payload.platform}, Cuenta: {payload.account_id} por el usuario {user_info.get('id', 'N/A')}")
    assert_org_access(session_data, payload.account_id)

    try:
        if payload.post_id:
            existing = get_post_by_id(payload.post_id)
            if existing:
                update_post(payload.post_id, {
                    "content": payload.content,
                    "status": "draft",
                    "platform": payload.platform,
                    "account_id": payload.account_id,
                    "scheduled_time": None,
                    "link_url": payload.link_url
                })
                post_id = payload.post_id
            else:
                post_id = create_post(
                    content=payload.content,
                    status="draft",
                    platform=payload.platform,
                    account_id=payload.account_id,
                    scheduled_time=None,
                    link_url=payload.link_url,
                    post_id=payload.post_id
                )
        else:
            # Persistencia en BD de registro en estado borrador.
            post_id = create_post(
                content=payload.content,
                status="draft",
                platform=payload.platform,
                account_id=payload.account_id,
                scheduled_time=None,
                link_url=payload.link_url
            )
        return {"status": "success", "message": "Borrador guardado correctamente.", "post_id": post_id}
    except Exception as e:
        logger.error(f"Error al guardar borrador: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno al guardar borrador: {str(e)}")


class ModerationCheck(BaseModel):
    status: str = Field(description="Must be 'ALLOW' if the prompt is safe and ethical, or 'BLOCK' if it violates political ethics, promotes violence, magnicides, hatred, or human rights violations.")
    reason: str = Field(default="", description="A short explanation in Spanish of why the prompt is blocked. Leave empty if status is ALLOW.")

MODERATION_SYSTEM_PROMPT = """Eres el Revisor de Ética y Moderación de PostFast.
Tu labor es examinar la petición (prompt) de generación de post de LinkedIn enviada por el usuario.
Debes BLOQUEAR (BLOCK) cualquier petición que vaya en contra de la ética política o atente contra los derechos humanos.
Específicamente, debes bloquear:
1. Peticiones que promuevan, sugieran, justifiquen, bromeen o alienten el asesinato, magnicidio, daño físico, secuestro, tortura o violencia contra políticos, figuras públicas o cualquier ser humano (ej. "matar a Trump", "atentar contra políticos").
2. Contenido de odio, discriminación racial, sexual, de género, de orientación sexual, de nacionalidad, de religión, o acoso.
3. Promoción explícita de violaciones de derechos humanos, crímenes de guerra o apología de la violencia.

Si la petición es aceptable y no viola estos criterios (por ejemplo, hablar de negocios, tecnología, humor sano, marketing, bolsa de valores, etc.), debes PERMITIRLA (ALLOW).

Responde en el formato estructurado requerido.
"""

def check_prompt_moderation(prompt_text: str) -> ModerationCheck:
    if not prompt_text or not prompt_text.strip():
        return ModerationCheck(status="ALLOW", reason="")
        
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.prompts import ChatPromptTemplate
        from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
        
        llm = ChatGoogleGenerativeAI(
            model=MEDIUM_LLM,
            google_api_key=GENAI_API_KEY,
            temperature=0.0
        )
        structured_llm = llm.with_structured_output(ModerationCheck)
        prompt = ChatPromptTemplate.from_messages([
            ("system", MODERATION_SYSTEM_PROMPT),
            ("human", "Petición del usuario: {query}")
        ])
        chain = prompt | structured_llm
        result = chain.invoke({"query": prompt_text})
        return result
    except Exception as e:
        logger.error(f"Error en la pre-moderación del prompt: {e}")
        return ModerationCheck(status="ALLOW", reason="")


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
    
    # 1. Moderación ética previa del prompt
    moderation = check_prompt_moderation(payload.query)
    if moderation.status == "BLOCK":
        logger.warning(f"Petición bloqueada por moderación. Prompt: '{payload.query}'. Razón: {moderation.reason}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contenido rechazado: {moderation.reason}"
        )

    # Registro de acceso multi-tenant: el usuario opera esta organización con su propio token.
    org_urn = (payload.selected_account or {}).get("urn", "")
    if org_urn:
        register_org_access(session_data, org_urn)

    # Persistencia a largo plazo: la 'URL de referencia' del formulario se ingesta
    # automáticamente en el RAG (asíncrono; no bloquea ni condiciona la generación).
    if payload.link_url and org_urn:
        try:
            from src.tasks import ingest_url_task
            ingest_url_task.delay(org_urn=org_urn, url=payload.link_url)
            logger.info("[generate_post] URL de referencia encolada para ingesta RAG: %s", payload.link_url)
        except Exception as ingest_exc:
            logger.warning("[generate_post] No se pudo encolar la ingesta de la URL: %s", ingest_exc)

    payload_dict = payload.model_dump()

    # Inyectar explícitamente el token de acceso OAuth en el payload
    # dado que el worker de Celery no comparte contexto con FastAPI.
    user_token_data = session_data.get("token_data", {})
    payload_dict["access_token"] = session_data.get("linkedin_access_token") or user_token_data.get("access_token", "")

    # Invocación asíncrona; .delay() retorna el descriptor AsyncResult.
    # NOTA: no loguear payload_dict completo (contiene el token OAuth).
    logger.info(
        "[AI LangGraph] Encolando tarea de generación para org=%s (query de %d caracteres).",
        org_urn or "N/A", len(payload.query or ""),
    )
    task = content_generation_task.delay(payload_dict=payload_dict)

    logger.info(f"El usuario {user_info.get('id', 'N/A')} ha encolado la tarea {task.id}.")

    return {"task_id": task.id}

@content_router.get("/generate_post/status/{task_id}")
async def get_generation_status(
    task_id: str,
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Consulta activamente el Result Backend (Redis) para determinar el estado de una tarea asíncrona.

    Requiere sesión válida: los borradores generados no deben ser legibles
    por terceros que capturen o adivinen un task_id.

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


@content_router.post("/generate_post/stop/{task_id}")
async def stop_generation_endpoint(
    task_id: str,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Aborta/cancela una tarea de generación de contenido Celery activa.
    """
    logger.info(f"Petición para detener la generación de la tarea: {task_id}")
    try:
        from src.celery_app import celery_app
        celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
        logger.info(f"Tarea {task_id} revocada exitosamente.")
        return {"status": "success", "message": "Generación detenida correctamente."}
    except Exception as e:
        logger.error(f"Error al detener la tarea {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudo detener la generación: {str(e)}")


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

def _get_post_checking_access(post_id: str, session_data: dict) -> Dict[str, Any]:
    """Recupera un post y verifica que su cuenta pertenece al usuario de la sesión."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    assert_org_access(session_data, post.get("account_id", ""))
    return post


@content_router.post("/posts", response_model=str)
async def create_post_endpoint(payload: PostCreatePayload, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Crea un nuevo registro de post en la base de datos.

    :param payload: Modelo Pydantic con los datos del post.
    :param session_data: Sesión del usuario inyectada.
    :returns: Identificador UUID del post creado.
    """
    assert_org_access(session_data, payload.account_id)
    post_id = create_post(**payload.model_dump())
    return post_id

@content_router.get("/posts", response_model=List[Dict[str, Any]])
async def list_posts_endpoint(status: Optional[str] = None, account_id: Optional[str] = None, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Lista los posts creados por el usuario, filtrables por status o account_id.

    Sin account_id explícito, el resultado se limita a las cuentas vinculadas
    al usuario de la sesión (aislamiento multi-tenant).

    :param status: Opcional. Filtro por estado (ej. 'published', 'scheduled').
    :param account_id: Opcional. Filtro por cuenta asociada.
    :param session_data: Sesión del usuario inyectada.
    :returns: Lista de diccionarios con la metadata de cada post.
    """
    if account_id:
        assert_org_access(session_data, account_id)
        return get_all_posts(status=status, account_id=account_id)

    user_orgs = set(get_user_org_urns(session_data))
    all_posts = get_all_posts(status=status, account_id=None)
    return [p for p in all_posts if p.get("account_id") in user_orgs]

# NOTA: esta ruta debe declararse ANTES de '/posts/{post_id}' — de lo contrario
# FastAPI enruta '/posts/count' al handler dinámico con post_id='count'.
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
    assert_org_access(session_data, account_id)
    count = get_posts_count_by_account(account_id)
    return {"count": count}

@content_router.get("/posts/{post_id}", response_model=Dict[str, Any])
async def get_post_endpoint(post_id: str, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Recupera un post específico según su ID.

    :param post_id: Identificador único del post.
    :param session_data: Sesión del usuario inyectada.
    :returns: Diccionario con la información del post.
    :raises HTTPException: Si el post no es encontrado (404).
    """
    return _get_post_checking_access(post_id, session_data)

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
    _get_post_checking_access(post_id, session_data)
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
    _get_post_checking_access(post_id, session_data)
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
    except Exception:
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
    :returns: Lista de diccionarios con la metadata extraída de cada empresa
              (limitada a las organizaciones vinculadas al usuario).
    """
    try:
        user_orgs = set(get_user_org_urns(session_data))
        profiles = get_all_company_profiles()
        return [p for p in profiles if p.get("org_urn") in user_orgs]
    except Exception:
        logger.exception("Error listando company_profiles")
        raise HTTPException(status_code=500, detail="Error recuperando perfiles de empresa")


def enrich_company_profile_if_needed(profile: dict) -> dict:
    org_urn = profile.get("org_urn")
    company_profile = profile.get("company_profile") or {}
    
    # Ensure logo_url is always populated in company_profile if present in raw_batch_data
    raw_batch_data = profile.get("raw_batch_data") or {}
    logo_url = None
    if isinstance(raw_batch_data, dict):
        logo_url = raw_batch_data.get("logo_url")
        if not logo_url and "organization" in raw_batch_data and isinstance(raw_batch_data["organization"], dict):
            logo_url = raw_batch_data["organization"].get("logo_url")
            
    if logo_url:
        if company_profile.get("logo_url") != logo_url:
            company_profile["logo_url"] = logo_url
            profile["company_profile"] = company_profile
            
    about_us = company_profile.get("about_us_content")
    specialties = company_profile.get("specialties")
    
    has_about_us = bool(about_us and about_us.strip())
    has_specialties = bool(specialties and len(specialties) > 0)
    
    if has_about_us and has_specialties:
        return profile
        
    try:
        from src.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        
        # Get all indexed knowledge content to synthesize
        result = supabase.table("company_knowledge").select("source_type, content").eq("org_urn", org_urn).execute()
        rows = result.data or []
        
        if not rows:
            return profile
            
        doc_texts = []
        for r in rows:
            if r.get("source_type") in ("pdf_document", "brand_book", "product_catalog", "about_us"):
                doc_texts.append(f"[{r.get('source_type')}]: {r.get('content')}")
                
        if not doc_texts:
            return profile
            
        context = "\n\n".join(doc_texts)[:8000]
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
        import json
        
        llm = ChatGoogleGenerativeAI(model=MEDIUM_LLM, google_api_key=GENAI_API_KEY, temperature=0.2)
        prompt = f"""
        Dado el siguiente contenido de la base de conocimientos de la empresa, sintetiza:
        1. Un resumen sobre nosotros (about_us_content) de unas 150-200 palabras, redactado en español profesional, describiendo a qué se dedica la empresa, su misión y propuesta de valor.
        2. Una lista de especialidades (specialties) de la empresa (máximo 8 términos cortos, ej. ["IoT Agrícola", "Riego Inteligente"]).

        **Contenido de la base de conocimientos:**
        {context}

        Devuelve un objeto JSON con exactamente estas dos claves: "about_us_content" y "specialties" (lista de strings).
        Ejemplo de salida:
        {{
            "about_us_content": "Descripción de la empresa...",
            "specialties": ["Especialidad 1", "Especialidad 2"]
        }}
        Devuelve EXCLUSIVAMENTE el JSON, sin formato markdown ni texto introductorio.
        """
        response = llm.invoke(prompt)
        res_text = response.content
        if isinstance(res_text, list):
            res_text = "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in res_text)
        res_text = res_text.strip()
        if res_text.startswith("```json"):
            res_text = res_text[7:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]
        res_text = res_text.strip()
        
        data = json.loads(res_text)
        
        if not has_about_us and data.get("about_us_content"):
            company_profile["about_us_content"] = data["about_us_content"]
        if not has_specialties and data.get("specialties"):
            company_profile["specialties"] = data["specialties"]
            
        profile["company_profile"] = company_profile
        
        supabase.table("company_profiles").update({"company_profile": company_profile}).eq("org_urn", org_urn).execute()
        logger.info(f"Perfil de empresa {org_urn} enriquecido dinámicamente usando RAG.")
    except Exception as e:
        logger.error(f"Error al enriquecer perfil dinámicamente: {e}")
        
    return profile

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
    assert_org_access(session_data, org_urn)
    profile = get_company_profile(org_urn)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontro perfil de empresa para el URN: {org_urn}. "
                   "Puede que la extraccion batch aun no haya terminado.",
        )
    profile = enrich_company_profile_if_needed(profile)
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
    # Sesiones de plataforma (provider='supabase'): el access_token de la sesión
    # es el JWT de Supabase; el token de LinkedIn viaja aparte en la sesión.
    user_token_data = session_data.get("token_data", {})
    access_token = session_data.get("linkedin_access_token") or user_token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Token de acceso no disponible en la sesion.")

    if payload.org_urn and payload.org_urn.startswith("urn:li:person:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Las cuentas personales no pueden sincronizar o simular RAG corporativo."
        )

    # El usuario opera esta organización con su propio token: registrar vínculo tenant.
    register_org_access(session_data, payload.org_urn)

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
    except Exception:
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

    # Sesiones de plataforma: usar el token de LinkedIn vinculado, no el JWT de Supabase.
    user_token_data = session_data.get("token_data", {})
    access_token = session_data.get("linkedin_access_token") or user_token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de acceso de LinkedIn en los datos de la sesion.",
        )

    assert_org_access(session_data, payload.org_urn)

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
    assert_org_access(session_data, org_urn)
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
    "/config",
    summary="Retorna la configuración pública para el cliente Supabase Realtime",
)
async def get_config_endpoint():
    """
    Retorna SUPABASE_URL y la clave PÚBLICA (anon/publishable) para que el
    frontend se conecte a los canales de Realtime Broadcast.

    La clave privilegiada de backend (SUPABASE_KEY) nunca se expone aquí:
    si no hay clave pública configurada, se devuelve null y el frontend
    degrada a polling HTTP.
    """
    from src.core.constants import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY
    if not SUPABASE_PUBLISHABLE_KEY:
        logger.critical(
            "SUPABASE_PUBLISHABLE_KEY / SUPABASE_ANON_KEY no configurada: "
            "el Realtime del frontend queda deshabilitado. Añádela al .env "
            "(Supabase > Settings > API > anon public key)."
        )
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_key": SUPABASE_PUBLISHABLE_KEY,
    }

# --- SKILLS ENDPOINTS ---

def _assert_skill_access(skill_id: str, session_data: dict) -> dict:
    """Recupera una skill y verifica que su organización pertenece al usuario."""
    skill = get_skill_by_id(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill no encontrada")
    assert_org_access(session_data, skill.get("org_urn", ""))
    return skill

@content_router.get("/skills")
async def get_skills_endpoint(org_urn: str, session_data: dict = Depends(get_current_session_data_from_token)):
    assert_org_access(session_data, org_urn)
    return get_all_skills(org_urn)

@content_router.post("/skills")
async def create_skill_endpoint(payload: SkillCreatePayload, session_data: dict = Depends(get_current_session_data_from_token)):
    assert_org_access(session_data, payload.org_urn)
    skill_id = create_skill(payload.org_urn, payload.name, payload.description, payload.markdown_content)
    if not skill_id:
        raise HTTPException(status_code=500, detail="Error creating skill")
    return {"skill_id": skill_id}

@content_router.put("/skills/{skill_id}")
async def update_skill_endpoint(skill_id: str, payload: SkillUpdatePayload, session_data: dict = Depends(get_current_session_data_from_token)):
    _assert_skill_access(skill_id, session_data)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    success = update_skill(skill_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Error updating skill")
    return {"success": True}

@content_router.delete("/skills/{skill_id}")
async def delete_skill_endpoint(skill_id: str, session_data: dict = Depends(get_current_session_data_from_token)):
    _assert_skill_access(skill_id, session_data)
    success = delete_skill(skill_id)
    if not success:
        raise HTTPException(status_code=500, detail="Error deleting skill")
    return {"success": True}

# --- PDF UPLOAD ENDPOINT ---

@content_router.post("/company/upload_pdf")
async def upload_company_pdf_endpoint(
    org_urn: str,
    file: UploadFile = File(...),
    session_data: dict = Depends(get_current_session_data_from_token)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    assert_org_access(session_data, org_urn)

    try:
        # Read PDF content
        pdf_bytes = await file.read()

        # Save physical file locally
        import os
        from src.core.constants import UPLOAD_DIR
        safe_org_urn = org_urn.replace(":", "_")
        safe_filename = os.path.basename(file.filename)
        upload_dir = os.path.join(UPLOAD_DIR, safe_org_urn)
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
            
        # Extract text content from PDF
        pdf_file_obj = io.BytesIO(pdf_bytes)
        reader = pypdf.PdfReader(pdf_file_obj)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
            
        # Index text content using existing service logic
        from src.services.rag_service import index_document
        
        metadata = {
            "filename": file.filename,
            "org_urn": org_urn
        }
        
        result = index_document(
            org_urn=org_urn,
            source_type="pdf_document",
            source_id=file.filename,
            content=text_content,
            metadata=metadata
        )
        return {"success": True, "message": f"Indexed {file.filename}"}
    except Exception as e:
        logger.error(f"Error processing PDF {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- RAG: ENLACES DE INTERÉS (URLs) ---

class IngestUrlPayload(BaseModel):
    org_urn: str
    url: str


@content_router.post("/company/ingest_url")
async def ingest_url_endpoint(
    payload: IngestUrlPayload,
    session_data: dict = Depends(get_current_session_data_from_token),
):
    """
    Ingesta síncrona de una URL en la base de conocimiento (alta manual desde la UI).
    Extrae el contenido principal de la página, lo limpia y lo vectoriza en el RAG.
    """
    assert_org_access(session_data, payload.org_urn)
    from src.services.url_ingestion import ingest_url, URLIngestionError
    try:
        result = ingest_url(payload.org_urn, payload.url)
        return {"success": True, **result}
    except URLIngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Error ingiriendo URL %s", payload.url)
        raise HTTPException(status_code=500, detail=f"Error indexando la URL: {exc}")


@content_router.get("/company/urls")
async def get_company_urls_endpoint(org_urn: str, session_data: dict = Depends(get_current_session_data_from_token)):
    """Lista los enlaces de interés indexados en el RAG (deduplicados por URL)."""
    assert_org_access(session_data, org_urn)
    try:
        from src.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        result = (
            supabase.table("company_knowledge")
            .select("source_id, metadata, created_at")
            .eq("org_urn", org_urn)
            .eq("source_type", "web_page")
            .execute()
        )
        urls: dict = {}
        for row in (result.data or []):
            base = row["source_id"].split("#chunk_")[0]
            if base not in urls:
                meta = row.get("metadata") or {}
                urls[base] = {
                    "url": base,
                    "title": meta.get("title") or base,
                    "created_at": row["created_at"],
                }
        return sorted(urls.values(), key=lambda u: u["created_at"], reverse=True)
    except Exception as exc:
        logger.error("Error listando URLs del RAG: %s", exc)
        raise HTTPException(status_code=500, detail="Error recuperando los enlaces indexados")


@content_router.delete("/company/urls")
async def delete_company_url_endpoint(org_urn: str, url: str, session_data: dict = Depends(get_current_session_data_from_token)):
    """Elimina un enlace (y todos sus chunks) de la base de conocimiento."""
    assert_org_access(session_data, org_urn)
    try:
        from src.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        supabase.table("company_knowledge").delete().eq("org_urn", org_urn).eq("source_type", "web_page").eq("source_id", url).execute()
        supabase.table("company_knowledge").delete().eq("org_urn", org_urn).eq("source_type", "web_page").like("source_id", f"{url}#chunk_%").execute()
        return {"success": True}
    except Exception as exc:
        logger.error("Error eliminando URL del RAG: %s", exc)
        raise HTTPException(status_code=500, detail="Error eliminando el enlace")


@content_router.get("/company/documents")
async def get_company_documents_endpoint(org_urn: str, session_data: dict = Depends(get_current_session_data_from_token)):
    # Get unique document names from company_knowledge where source_type = 'pdf_document'
    assert_org_access(session_data, org_urn)
    try:
        from src.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        result = supabase.table("company_knowledge").select("source_id, created_at").eq("org_urn", org_urn).eq("source_type", "pdf_document").execute()
        # Deduplicate by base source_id (removing #chunk_ suffix)
        docs = {}
        for row in (result.data or []):
            sid = row["source_id"]
            base_name = sid.split("#chunk_")[0] if "#chunk_" in sid else sid
            if base_name not in docs:
                docs[base_name] = row["created_at"]
        return [{"filename": k, "created_at": v} for k, v in docs.items()]
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        raise HTTPException(status_code=500, detail="Error fetching documents")

@content_router.delete("/company/documents")
async def delete_company_document_endpoint(org_urn: str, filename: str, session_data: dict = Depends(get_current_session_data_from_token)):
    assert_org_access(session_data, org_urn)
    try:
        from src.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        result = supabase.table("company_knowledge").delete().eq("org_urn", org_urn).eq("source_type", "pdf_document").eq("source_id", filename).execute()
        # Also clean up chunks if there were any
        supabase.table("company_knowledge").delete().eq("org_urn", org_urn).eq("source_type", "pdf_document").like("source_id", f"{filename}#chunk_%").execute()

        # Delete local physical file
        import os
        from src.core.constants import UPLOAD_DIR
        safe_org_urn = org_urn.replace(":", "_")
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(UPLOAD_DIR, safe_org_urn, safe_filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as fe:
                logger.warning(f"Could not delete physical PDF file {file_path}: {fe}")
                
        return {"success": True}
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail="Error deleting document")


@content_router.get("/company/documents/pdf")
async def get_company_document_pdf_endpoint(
    org_urn: str,
    filename: str,
    token: Optional[str] = None,
    session_data: dict = Depends(get_current_session_data_from_token_or_query)
):
    import os
    from src.core.constants import UPLOAD_DIR
    assert_org_access(session_data, org_urn)
    safe_org_urn = org_urn.replace(":", "_")
    safe_filename = os.path.basename(filename)
    upload_dir = os.path.join(UPLOAD_DIR, safe_org_urn)
    file_path = os.path.join(upload_dir, safe_filename)
    
    if not os.path.exists(file_path):
        logger.info(f"PDF {safe_filename} no encontrado físicamente en disco. Intentando reconstruir desde Supabase...")
        try:
            from src.services.supabase_client import get_supabase_admin
            supabase = get_supabase_admin()
            
            # Obtener registros de la base de datos
            result = supabase.table("company_knowledge")\
                .select("source_id, content")\
                .eq("org_urn", org_urn)\
                .eq("source_type", "pdf_document")\
                .execute()
            rows = result.data or []
            
            content = ""
            # 1. Intentar encontrar el documento completo
            full_doc = next((r for r in rows if r.get("source_id") == filename), None)
            if full_doc:
                content = full_doc["content"]
            else:
                # 2. Si no, concatenar los fragmentos (chunks)
                matching_rows = []
                for r in rows:
                    sid = r.get("source_id", "")
                    if sid.startswith(f"{filename}#chunk_"):
                        matching_rows.append(r)
                
                if matching_rows:
                    def get_chunk_idx(row):
                        sid = row.get("source_id", "")
                        if "#chunk_" in sid:
                            try:
                                return int(sid.split("#chunk_")[-1])
                            except ValueError:
                                return 999
                        return 0
                    matching_rows.sort(key=get_chunk_idx)
                    content = "\n\n".join([r.get("content", "") for r in matching_rows])
            
            if not content:
                logger.warning(f"No se encontró contenido o chunks para {filename} en company_knowledge.")
                raise HTTPException(status_code=404, detail="Archivo PDF no encontrado físicamente ni en la base de datos.")
            
            # Reconstruir archivo PDF usando ReportLab
            os.makedirs(upload_dir, exist_ok=True)
            
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            
            doc = SimpleDocTemplate(
                file_path,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72,
                title=filename
            )
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontName='Helvetica-Bold',
                fontSize=18,
                leading=22,
                textColor=colors.HexColor('#0F5132'),
                spaceAfter=15
            )
            
            section_style = ParagraphStyle(
                'DocSection',
                parent=styles['Heading2'],
                fontName='Helvetica-Bold',
                fontSize=12,
                leading=15,
                textColor=colors.HexColor('#198754'),
                spaceBefore=10,
                spaceAfter=5
            )
            
            body_style = ParagraphStyle(
                'DocBody',
                parent=styles['BodyText'],
                fontName='Helvetica',
                fontSize=10,
                leading=14,
                textColor=colors.HexColor('#212529'),
                spaceAfter=8
            )
            
            story = []
            story.append(Paragraph(filename, title_style))
            story.append(Spacer(1, 10))
            
            # Dividir por líneas y poblar
            paragraphs = content.split('\n')
            for p in paragraphs:
                p_str = p.strip()
                if not p_str:
                    continue
                if p_str.startswith('## '):
                    story.append(Paragraph(p_str[3:], section_style))
                elif p_str.startswith('# '):
                    story.append(Paragraph(p_str[2:], title_style))
                else:
                    story.append(Paragraph(p_str, body_style))
            
            doc.build(story)
            logger.info(f"PDF {safe_filename} reconstruido y guardado exitosamente en {file_path}")
            
        except HTTPException as http_exc:
            raise http_exc
        except Exception as err:
            logger.error(f"Fallo al restaurar y compilar PDF {filename} desde BD: {err}", exc_info=True)
            raise HTTPException(status_code=404, detail="Archivo PDF no encontrado físicamente y falló su reconstrucción.")
            
    from fastapi import Response
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"',
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

@content_router.get("/company/documents/content")
async def get_company_document_content_endpoint(
    org_urn: str,
    filename: str,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    assert_org_access(session_data, org_urn)
    try:
        from src.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()

        result = supabase.table("company_knowledge").select("source_id, content").eq("org_urn", org_urn).eq("source_type", "pdf_document").execute()
        rows = result.data or []
        
        # 1. Try to find the full un-sliced document first
        full_doc = next((r for r in rows if r.get("source_id") == filename), None)
        if full_doc:
            return {"filename": filename, "content": full_doc["content"]}
            
        # 2. Fallback to chunk concatenation
        matching_rows = []
        for r in rows:
            sid = r.get("source_id", "")
            if sid.startswith(f"{filename}#chunk_"):
                matching_rows.append(r)
                
        if not matching_rows:
            raise HTTPException(status_code=404, detail="Document content not found")
            
        def get_chunk_idx(row):
            sid = row.get("source_id", "")
            if "#chunk_" in sid:
                try:
                    return int(sid.split("#chunk_")[-1])
                except ValueError:
                    return 999
            return 0
            
        matching_rows.sort(key=get_chunk_idx)
        # Avoid duplicated joining of overlap using remove_overlap
        content = ""
        for r in matching_rows:
            chunk = r["content"]
            if not content:
                content = chunk
            else:
                content = remove_overlap(content, chunk)
        return {"filename": filename, "content": content}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching document content: {e}")
        raise HTTPException(status_code=500, detail="Error fetching document content")

class BrandAssetsUpdatePayload(BaseModel):
    org_urn: str
    brand_book: Optional[str] = None
    about_us_content: Optional[str] = None
    specialties: Optional[list[str]] = None

@content_router.get("/company/brand_assets")
async def get_company_brand_assets_endpoint(org_urn: str, session_data: dict = Depends(get_current_session_data_from_token)):
    """
    Activos de marca editables desde la UI. NOTA: el catálogo de servicios se
    eliminó del producto — la información de servicios proviene exclusivamente
    de los PDFs y URLs que el usuario indexa en el RAG.
    """
    assert_org_access(session_data, org_urn)
    try:
        brand_book = get_brand_asset_content(org_urn, "brand_book")

        default_brand_book = """# Guía de Estilo y Do's & Don'ts de LinkedIn
**Valores de Marca:**
- Innovación Tecnológica con Foco Humano.
- Rigurosidad y Factualidad (prohibido alucinar o mentar promesas falsas).
- Transparencia Total en Resultados.

**Tono Editorial Recomendado:**
- Profesional, asertivo, centrado en valor tecnológico real.
- Uso de ganchos (hooks) lógicos basados en problemas del sector.

**Recomendaciones de Formato en LinkedIn:**
- **Do's:** Párrafos de 1-2 líneas, uso estratégico de emojis técnicos (💻, 🧠, 📈, 🚀), CTA al final del post con enlaces limpios.
- **Don'ts:** Evitar tecnicismos vacíos, no citar nombres de clientes reales sin consentimiento explícito, jamás difamar competidores."""

        return {
            "brand_book": brand_book if brand_book else default_brand_book,
        }
    except Exception as e:
        logger.error(f"Error fetching brand assets: {e}")
        raise HTTPException(status_code=500, detail="Error fetching brand assets")

def get_brand_asset_content(org_urn: str, source_type: str) -> str:
    from src.services.supabase_client import get_supabase_admin
    supabase = get_supabase_admin()
    result = supabase.table("company_knowledge").select("source_id, content").eq("org_urn", org_urn).eq("source_type", source_type).execute()
    rows = result.data or []
    if not rows:
        return ""
    
    # 1. Try to find the full un-sliced document row first
    full_doc = next((r for r in rows if "#chunk_" not in r.get("source_id", "")), None)
    if full_doc:
        return full_doc["content"]
        
    # 2. Fallback to chunk concatenation with overlap removal
    def get_chunk_idx(row):
        source_id = row.get("source_id", "")
        if "#chunk_" in source_id:
            try:
                return int(source_id.split("#chunk_")[-1])
            except ValueError:
                return 999
        return 0
        
    rows.sort(key=get_chunk_idx)
    content = ""
    for r in rows:
        chunk = r["content"]
        if not content:
            content = chunk
        else:
            content = remove_overlap(content, chunk)
    return content

@content_router.post("/company/brand_assets")
async def update_company_brand_assets_endpoint(payload: BrandAssetsUpdatePayload, session_data: dict = Depends(get_current_session_data_from_token)):
    assert_org_access(session_data, payload.org_urn)
    try:
        from src.services.supabase_client import get_supabase_admin
        from src.services.rag_service import index_document
        supabase = get_supabase_admin()
        
        if payload.brand_book is not None:
            supabase.table("company_knowledge").delete().eq("org_urn", payload.org_urn).eq("source_type", "brand_book").execute()
            if payload.brand_book.strip():
                index_document(
                    org_urn=payload.org_urn,
                    source_type="brand_book",
                    source_id="generated_brand_book",
                    content=payload.brand_book,
                    metadata={"edited": True}
                )
                
        if payload.about_us_content is not None or payload.specialties is not None:
            profile_res = supabase.table("company_profiles").select("company_profile").eq("org_urn", payload.org_urn).execute()
            if profile_res.data:
                existing_row = profile_res.data[0]
                company_profile = existing_row.get("company_profile") or {}
                
                if isinstance(company_profile, str):
                    try:
                        import json
                        company_profile = json.loads(company_profile)
                    except Exception:
                        company_profile = {}
                
                if payload.about_us_content is not None:
                    company_profile["about_us_content"] = payload.about_us_content
                if payload.specialties is not None:
                    company_profile["specialties"] = payload.specialties
                    
                supabase.table("company_profiles").update({"company_profile": company_profile}).eq("org_urn", payload.org_urn).execute()

        if payload.about_us_content is not None:
            supabase.table("company_knowledge").delete().eq("org_urn", payload.org_urn).eq("source_type", "about_us").execute()
            if payload.about_us_content.strip():
                index_document(
                    org_urn=payload.org_urn,
                    source_type="about_us",
                    source_id="about_us_manual",
                    content=payload.about_us_content,
                    metadata={"edited": True}
                )
                
        return {"success": True, "message": "Brand assets updated successfully"}
    except Exception as e:
        logger.error(f"Error updating brand assets: {e}")
        raise HTTPException(status_code=500, detail="Error updating brand assets")

# NOTA: el endpoint /company/generate_catalog_strategy y el concepto de
# 'Catálogo de Servicios' se eliminaron: la información de servicios proviene
# exclusivamente de los PDFs y URLs indexados en el RAG por el usuario.

@content_router.get("/company/rag_posts")
async def get_company_rag_posts_endpoint(
    org_urn: str,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    assert_org_access(session_data, org_urn)
    try:
        from src.services.supabase_client import get_supabase_admin
        supabase = get_supabase_admin()
        result = supabase.table("company_knowledge").select("source_id, content, created_at, metadata").eq("org_urn", org_urn).eq("source_type", "linkedin_post").execute()
        rows = result.data or []
        
        # Group chunks by source_id
        grouped = {}
        for row in rows:
            sid = row["source_id"]
            base_id = sid.split("#chunk_")[0] if "#chunk_" in sid else sid
            if base_id not in grouped:
                grouped[base_id] = []
            grouped[base_id].append(row)
            
        posts = []
        for base_id, chunks in grouped.items():
            meta = chunks[0].get("metadata") or {}
            # Omitir posts que estén marcados explícitamente como no de referencia (ej. histórico demovido)
            if meta.get("is_reference") is False:
                continue
                
            score = meta.get("score", 70)
            
            def get_chunk_idx(row):
                sid = row.get("source_id", "")
                if "#chunk_" in sid:
                    try:
                        return int(sid.split("#chunk_")[-1])
                    except ValueError:
                        return 999
                return 0
            chunks.sort(key=get_chunk_idx)
            full_content = "\n\n".join(c["content"] for c in chunks)
            
            # Remove redundant headers if index_document added one
            clean_content = full_content
            prefix = "Post publicado anteriormente con alto engagement:\n"
            if clean_content.startswith(prefix):
                clean_content = clean_content[len(prefix):]
            
            posts.append({
                "id": base_id,
                "content": clean_content,
                "created_at": chunks[0]["created_at"],
                "score": score
            })
            
        posts.sort(key=lambda x: x["score"], reverse=True)
        return posts
    except Exception as e:
        logger.error(f"Error fetching RAG posts: {e}")
        raise HTTPException(status_code=500, detail="Error fetching RAG posts")
