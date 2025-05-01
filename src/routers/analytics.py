from fastapi import APIRouter, HTTPException, Depends # Añadir Depends
from pydantic import BaseModel, Field, validator # Para definir el modelo del payload
from typing import Optional
from datetime import date # Para validar fechas

from src.core.logger import logger
from src.celery_app import celery_app
from src.tasks import run_etl_pipeline_task
from celery.result import AsyncResult

try:
    from src.auth import get_current_session_data_from_token
    # O si está en otro sitio: from src.auth import get_current_session_data_from_token
except ImportError:
    logger.critical("Could not import get_current_session_data_from_token dependency for analytics router!")
    # Definir un dummy para evitar error al cargar, pero fallará en runtime
    async def get_current_session_data_from_token():
        raise NotImplementedError("Auth dependency not loaded")

analytics_router = APIRouter()

# --- Modelo Pydantic para el Payload de trigger_etl ---
class EtlTriggerPayload(BaseModel):
    platform: str
    account_id: str
    start_date: date # FastAPI validará y convertirá 'YYYY-MM-DD' a objeto date
    end_date: date   # FastAPI validará y convertirá 'YYYY-MM-DD' a objeto date
    page_access_token: Optional[str] = None # Opcional, por defecto None

    # Ejemplo de validación extra
    @validator('end_date')
    def end_date_must_be_after_start_date(cls, end_date, values):
        start_date = values.get('start_date')
        if start_date and end_date < start_date:
            raise ValueError('End date must be after start date')
        return end_date


# --- API Endpoints for Tasks ---
# Trigger ETL
@analytics_router.post("/trigger_etl")
async def trigger_etl(
    payload: EtlTriggerPayload, # Usar el modelo Pydantic para el cuerpo
    session_data: dict = Depends(get_current_session_data_from_token) # Obtener sesión validada
):
    """
    Trigger the Celery ETL task.
    Obtiene el token de acceso de la sesión validada, no del payload.
    """
    user_access_token = session_data.get("token_data", {}).get("access_token")
    user_info = session_data.get("user_info", {})
    user_id_log = user_info.get('sub', 'N/A') # Para logging

    if not user_access_token:
        # Esto no debería ocurrir si la dependencia funciona, pero es una buena verificación
        logger.error(f"User {user_id_log} tried to trigger ETL but access token was missing in validated session data.")
        raise HTTPException(status_code=500, detail="Internal error: Access token missing in session.")

    logger.info(f"User {user_id_log} requested ETL trigger for {payload.platform}, Account: {payload.account_id}")

    try:
        # Convertir fechas date a string para Celery si la tarea lo espera así
        start_date_str = payload.start_date.strftime('%Y-%m-%d')
        end_date_str = payload.end_date.strftime('%Y-%m-%d')

        # Preparar argumentos para la tarea Celery
        # El token principal es el del usuario (de la sesión)
        # El page_access_token viene del payload (solo relevante para FB)
        task_args = [
            payload.platform,
            payload.account_id,
            user_access_token, # Usar el token de la sesión validada
            start_date_str,
            end_date_str
        ]
        task_kwargs = {}
        if payload.page_access_token:
            task_kwargs["page_access_token"] = payload.page_access_token

        # Llamar a la tarea Celery
        task = run_etl_pipeline_task.delay(*task_args, **task_kwargs)

        logger.info(f"ETL task triggered for {payload.platform}, Account: {payload.account_id}. Task ID: {task.id}")
        return {"task_id": task.id, "message": "ETL task started in background."}

    except Exception as e:
        logger.exception(f"Failed to trigger ETL task for user {user_id_log}, platform {payload.platform}, account {payload.account_id}")
        raise HTTPException(status_code=500, detail="Failed to start ETL task")


# Get Task Status
@analytics_router.get("/tasks/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a Celery task."""
    logger.debug(f"Requesting status for task ID: {task_id}")
    task_result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": None
    }

    if task_result.successful():
        response["result"] = task_result.get()
        logger.debug(f"Task {task_id} completed successfully. Result: {response['result']}")
    elif task_result.failed():
        # Access the error trace (can be large)
        try:
            # task_result.get() will raise the original exception
            task_result.get()
        except Exception as e:
            # Log the actual exception if possible
            logger.error(f"Task {task_id} failed.", exc_info=True) # Log with traceback
            # Return only the error message to the client
            response["result"] = {"error": str(e), "traceback": task_result.traceback} # Return traceback for debug
        logger.error(f"Task {task_id} failed. Status: {task_result.status}")

    # Other states: PENDING, STARTED, RETRY
    else:
        logger.debug(f"Task {task_id} status: {task_result.status}")

    return response