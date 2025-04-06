from fastapi import APIRouter, HTTPException, Request, Depends # Añadir Depends
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage
from src.core.logger import logger
from src.celery_app import celery_app
from src.tasks import publish_post_task
from datetime import datetime, timezone

# Importar la dependencia de autenticación
try:
     # Asumiendo que está en main.py en el directorio superior
     from src.auth import get_current_session_data_from_token
except ImportError:
     # Fallback o error si la estructura es diferente
     logger.critical("Could not import get_current_session_data_from_token dependency!")
     # Define un dummy para que FastAPI no falle al cargar, pero lanzará error en runtime
     async def get_current_session_data_from_token():
          raise NotImplementedError("Auth dependency not loaded")

content_router = APIRouter(
    prefix="/content",
    tags=["Content Generation & Scheduling"],
    # Aplicar dependencia globalmente si todos los endpoints la necesitan
    dependencies=[Depends(get_current_session_data_from_token)]
)

# --- Modelos Pydantic para Payloads ---
class SchedulePostPayload(BaseModel):
    platform: str # Ya no es necesario si lo obtenemos del token? Podría ser útil para verificar.
    account_id: str # ID de la página/org 
    content: str
    scheduled_time_str: Optional[str] = None # ISO 8601 format
    page_access_token: Optional[str] = None # Solo para FB, enviado explícitamente si es necesario
    image_url: Optional[str] = None # Para IG (o posts con imagen en otras plat.)
    link_url: Optional[str] = None # Para posts con enlaces

class QueryRequest(BaseModel):
    query: str

# --- Endpoints ---
@content_router.post("/schedule_post")
async def schedule_post_endpoint(
    payload: SchedulePostPayload, # Recibir payload como modelo Pydantic
    session_data: dict = Depends(get_current_session_data_from_token) # AUTENTICACIÓN
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
    # Para FB, usar page_access_token si se proporciona en el payload, sino el token de usuario.
    # Para LI, usar siempre el token de usuario.
    token_for_api = user_access_token
    if payload.platform.lower() == "facebook" and payload.page_access_token:
         logger.debug("Using provided Facebook page access token for the API call.")
         token_for_api = payload.page_access_token
    elif payload.platform.lower() == "facebook":
         logger.debug("Using Facebook user access token for the API call (no page token provided).")
         # Considerar si esto es un error - ¿la API de página requiere token de página? Probablemente sí.
         # raise HTTPException(status_code=400, detail="Facebook page access token required for posting.")

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
            try: scheduled_dt = datetime.fromisoformat(payload.scheduled_time_str.replace('Z', '+00:00'))
            except ValueError: scheduled_dt_naive = datetime.fromisoformat(payload.scheduled_time_str); scheduled_dt = scheduled_dt_naive.replace(tzinfo=timezone.utc)

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


# Asegurarse que este endpoint también esté protegido si es necesario
@content_router.post("/generate_post")
async def generate_post_endpoint(
    request: QueryRequest,
    fastapi_request: Request,
    session_data: dict = Depends(get_current_session_data_from_token) # <-- AÑADIR PROTECCIÓN
):
    """
    Generates post content using LangGraph. Requires authentication.
    """
    user_info = session_data.get("user_info", {})
    logger.info(f"Content generation requested by user {user_info.get('id', 'N/A')}: '{request.query[:50]}...'")
    try:
        app = fastapi_request.app
        graph = app.state.graph # Asume que el grafo está en app.state

        thread = {"configurable": {"thread_id": "user_" + str(user_info.get('id', 'anonymous'))}} # Usar ID de usuario para thread_id

        input_data = {"messages": [HumanMessage(content=request.query)]}
        response = await graph.ainvoke(input_data, thread)

        output_content = response.get("output") if isinstance(response, dict) else str(response)
        logger.debug(f"LangGraph raw response: {response}")

        return {"query": request.query, "response": output_content}

    except Exception as e:
        logger.exception(f"Error processing content generation request: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating content: {e}")