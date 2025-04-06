from src.core.logger import logger
from src.celery_app import celery_app
from src.tasks import run_etl_pipeline_task

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

analytics_router = APIRouter(
    prefix="/analytics",
    tags=["Analytics & Tasks"]
)

# --- API Endpoints for Tasks ---
# Trigger ETL
@analytics_router.post("/trigger_etl")
async def trigger_etl(platform: str, account_id: str, access_token: str, start_date: str, end_date: str, page_access_token: str = None):
    """Trigger the Celery ETL task."""
    logger.info(f"Received request to trigger ETL for {platform}, Account: {account_id}")
    try:
        # Pass all necessary args to the task, including page_access_token if it exists
        task_kwargs = {"page_access_token": page_access_token} if page_access_token else {}
        task = run_etl_pipeline_task.delay(platform, account_id, access_token, start_date, end_date, **task_kwargs)
        logger.info(f"ETL task triggered for {platform}, Account: {account_id}. Task ID: {task.id}")
        return {"task_id": task.id, "message": "ETL task started in background."}
    except Exception as e:
        logger.exception("Failed to trigger ETL task")
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