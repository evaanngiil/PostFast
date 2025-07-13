from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel, Field
from typing import Optional
from langchain_core.messages import HumanMessage
from src.core.logger import logger
from src.celery_app import celery_app
from src.tasks import publish_post_task
from datetime import datetime, timezone

import uuid
from fastapi import APIRouter, Depends
from src.dependencies.graph import get_graph
from src.tasks import content_generation_task


# Importar la dependencia de autenticación
try:
     # Asumiendo que está en main.py en el directorio superior
     from src.auth import get_current_session_data_from_token
except ImportError:
     # Fallback o error si la estructura es diferente
     logger.critical("Could not import get_current_session_data_from_token dependency!")
     # Define un dummy para que FastAPI no falle al cargar, pero lanzará error en runtime
     async def get_current_session_data_from_token(token: str | None = None):
          raise NotImplementedError("Auth dependency not loaded")

content_router = APIRouter()

# --- Modelos Pydantic para Payloads ---
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


class ResumePayload(BaseModel):
    task_id: str
    feedback: str # El feedback del usuario. Puede ser "aprobar" o un texto.


@content_router.post("/schedule_post")
async def schedule_post_endpoint(
    payload: SchedulePostPayload,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Schedule a post using Celery. Authenticated via Bearer token.
    Payload should NOT contain user access tokens.
    """
    user_info = session_data.get("user_info", {})
    user_token_data = session_data.get("token_data", {})
    user_access_token = user_token_data.get("access_token")
    session_provider = session_data.get("provider")

    logger.info(f"Received request to schedule post for platform {payload.platform}, Account: {payload.account_id} by user {user_info.get('id', 'N/A')}")

    # Validaciones
    if not user_access_token:
        raise HTTPException(status_code=401, detail="User access token missing in session data.")
    # Verificar que el payload.platform coincida con el provider del token
    if session_provider and payload.platform.lower() != session_provider.lower():
         logger.warning(f"Payload platform ({payload.platform}) mismatch with session provider ({session_provider}).")
         # Decidir si es un error o solo una advertencia
         # raise HTTPException(status_code=400, detail="Platform mismatch between payload and session.")

    # Determinar el token a usar para la API social
    # Para LI, usar siempre el token de usuario.
    token_for_api = user_access_token

    # Preparar argumentos para la tarea Celery
    task_args = [
        payload.platform,
        payload.account_id,
        token_for_api, # Token correcto para la API
        payload.content
    ]
    task_kwargs = {
        "image_url": payload.image_url,
        "link_url": payload.link_url # Pasar link_url a la tarea
        # Añadir otros kwargs que la tarea necesite
    }
    # Filtrar kwargs None
    task_kwargs = {k: v for k, v in task_kwargs.items() if v is not None}

    try:
        if payload.scheduled_time_str:
            try: 
                scheduled_dt = datetime.fromisoformat(payload.scheduled_time_str.replace('Z', '+00:00'))
            except ValueError: 
                scheduled_dt_naive = datetime.fromisoformat(payload.scheduled_time_str) 
                scheduled_dt = scheduled_dt_naive.replace(tzinfo=timezone.utc)

            if scheduled_dt <= datetime.now(timezone.utc):
                 logger.warning(f"Scheduled time {payload.scheduled_time_str} is in the past. Publishing now.")
                 task = publish_post_task.delay(*task_args, **task_kwargs)
                 msg = "Scheduled time is in the past, publishing task started now."
            else:
                task = publish_post_task.apply_async(args=task_args, kwargs=task_kwargs, eta=scheduled_dt)
                msg = f"Post scheduled successfully for {scheduled_dt.isoformat()}."
                logger.info(f"Post scheduling task created. Task ID: {task.id}, ETA: {scheduled_dt}")
        else: # Publish now
            task = publish_post_task.delay(*task_args, **task_kwargs)
            msg = "Post publication task started now."
            logger.info(f"Post publication task triggered immediately. Task ID: {task.id}")

        return {"task_id": task.id, "message": msg}

    except ValueError as ve:
         logger.error(f"Invalid scheduled time format: {payload.scheduled_time_str}. Error: {ve}")
         raise HTTPException(status_code=400, detail=f"Invalid scheduled time format: {payload.scheduled_time_str}. Use ISO 8601 format.")
    except Exception as e:
        logger.exception("Failed to schedule post task")
        raise HTTPException(status_code=500, detail="Failed to schedule post task")


# @content_router.post("/generate_post")
# async def generate_post_endpoint(
#     payload: ContentGenerationPayload,
#     request: Request,
#     graph = Depends(get_graph),
#     session_data: dict = Depends(get_current_session_data_from_token)
# ):
#     """
#     Generates post content using LangGraph, accepting a full context payload.
#     """
#     user_info = session_data.get("user_info", {})
#     logger.warning(f"[AI LangGraph] Content generation requested by user {user_info.get('id', 'N/A')} for account '{payload.account_name}'")


#     try:
#         thread_id = str(uuid.uuid4())
#         thread = {"configurable": {"thread_id": thread_id}}

#         # --- PASO 1: Transformar el payload de entrada (modelo Pydantic) al estado INTERNO inicial ---
#         initial_internal_state = {
#             "query": payload.query,
#             "tone": payload.tone,
#             "niche": payload.niche,
#             "account_name": payload.account_name,
#             "link_url": payload.link_url,
#             # Inicializar el resto de campos internos
#             "creative_brief": None,
#             "draft_content": None,
#             "refined_content": None,
#             "final_post": None,
#             "review_notes": "",
#             "revision_cycles": 0
#         }

#         logger.warning(f"[AI LangGraph] Invoking graph with thread ID {thread_id} and input: {initial_internal_state}")
        
#         # --- PASO 2: Invocar el grafo con el estado interno ---
#         final_internal_state = await graph.ainvoke(initial_internal_state, thread)

#         logger.debug(f"LangGraph raw response: {final_internal_state}")

#         # --- PASO 3: Transformar el estado interno final al payload de salida ---
#         final_content = final_internal_state.get("final_post", "Error: No se pudo generar el contenido final.")

#         return {"final_content": final_content}
#     except Exception as e:
#         logger.exception(f"Error processing content generation request: {e}")
#         raise HTTPException(status_code=500, detail=f"Error generating content: {e}")


@content_router.post(
    "/generate_post", 
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_post_start(
    payload: ContentGenerationPayload,
    session_data: dict = Depends(get_current_session_data_from_token)
):
    """
    Encola una tarea de generación de contenido en Celery y devuelve el ID de la tarea.
    """
    user_info = session_data.get("user_info", {})
    payload_dict = payload.model_dump()

    # .delay() devuelve un objeto AsyncResult que contiene el ID de la tarea
    task = content_generation_task.delay(payload_dict=payload_dict)

    logger.info(f"User {user_info.get('id', 'N/A')} enqueued task {task.id}.")

    return {"task_id": task.id}

@content_router.get("/generate_post/status/{task_id}")
async def get_generation_status(task_id: str):
    """

    Consulta el backend de resultados de Celery (Redis) para obtener el estado de una tarea.
    """
    task_result = celery_app.AsyncResult(task_id)

    if task_result.state == 'PENDING':
        # La tarea todavía no ha sido recogida por un worker o está en proceso.
        return {"status": "PENDING"}
    elif task_result.state == 'SUCCESS':
        # La tarea terminó con éxito. `task_result.result` contiene el valor devuelto.
        return {"status": "SUCCESS", "result": task_result.result}
    elif task_result.state == 'FAILURE':
        # La tarea falló. `task_result.result` contiene la excepción.
        return {"status": "FAILURE", "error": str(task_result.result)}
    elif task_result.state == 'PENDING_USER_INPUT':
        # La tarea está esperando input del usuario
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
    Reanuda una tarea de generación de contenido que fue interrumpida para recibir feedback humano.
    """
    # 1. Obtener el estado de la tarea original
    original_task_result = celery_app.AsyncResult(payload.task_id)
    if original_task_result.state != 'PENDING_USER_INPUT':
        raise HTTPException(status_code=400, detail="Task is not pending user input.")

    # 2. Extraer el checkpoint guardado
    checkpoint = original_task_result.info.get('checkpoint')
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found for the task.")

    # 3. Inyectar el feedback del usuario en el estado
    checkpoint['human_feedback'] = payload.feedback
    
    # 4. Lanzar la MISMA tarea, pero esta vez pasándole el checkpoint para que reanude
    # Usamos el mismo ID de tarea para que el resultado final sobreescriba el estado de interrupción.
    content_generation_task.apply_async(
        kwargs={"checkpoint": checkpoint}, # Pasamos el checkpoint como keyword argument
        task_id=payload.task_id
    )

    logger.info(f"Resuming task {payload.task_id} with user feedback.")
    return {"task_id": payload.task_id, "message": "Content generation task resumed."}