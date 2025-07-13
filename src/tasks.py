from src.celery_app import celery_app
from src.core.logger import logger
from src.data_processing import ( transform_and_load_instagram, transform_and_load_linkedin, get_db_connection)
from src.social_apis import (
     get_instagram_insights, get_linkedin_page_insights,
    post_to_instagram, post_to_linkedin_organization
)
from src.agents.content_agent.callbacks import TokenUsageCallback
from src.dependencies.graph import graph
from celery.exceptions import Ignore

from datetime import datetime, timezone
import time
import psycopg
import asyncio
import uuid

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5) # bind=True to access the task instance
def run_etl_pipeline_task(self, platform, account_id, access_token, start_date_str, end_date_str, **kwargs):
    """Celery task to run the ETL pipeline in the background."""

    log_prefix = f"[Task ID: {self.request.id}]"
    logger.info(f"{log_prefix} Starting ETL for {platform} - Account: {account_id} | Period: {start_date_str} to {end_date_str}")
    start_time = time.time()
    rows_processed = 0

    try:
        conn = get_db_connection()
        if not conn:
            raise ConnectionError("Failed to get PostgreSQL connection for ETL task.")

        start_date_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date_dt = datetime.strptime(end_date_str, '%Y-%m-%d')

        if platform == "Instagram":
            # NOTE: IG Insights requires page access token and IG User ID
            page_access_token = kwargs.get('page_access_token', access_token)
            ig_user_id = account_id # Assume that account_id is the IG User ID

            if not page_access_token: 
                raise ValueError("Missing page_access_token for Instagram ETL")

            raw_data = get_instagram_insights(ig_user_id, page_access_token, start_date_str, end_date_str)
            if raw_data:
                rows_processed = transform_and_load_instagram(raw_data, ig_user_id, conn)
       
        elif platform == "LinkedIn":
            # Verificar si el account_id es un URN de organización ANTES de llamar a la función de insights
            if account_id and isinstance(account_id, str) and account_id.startswith("urn:li:organization:"):
                org_urn = account_id
                logger.info(f"{log_prefix} Account {org_urn} is a LinkedIn Organization URN. Fetching page insights...")

                start_ts = int(start_date_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                end_ts = int(end_date_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

                raw_data = None # Inicializar raw_data
                try:
                    # Llamar a la función API (ahora devuelve None si el URN es inválido o si las llamadas fallan)
                    raw_data = get_linkedin_page_insights(org_urn, access_token, start_ts, end_ts)
                    # Loguear si se recibió algo (incluso un dict con None dentro)
                    logger.info(f"{log_prefix} LinkedIn insights API call completed for Org {org_urn}. Data received: {raw_data is not None}")

                except Exception as api_exc:
                    # Capturar excepciones inesperadas de la llamada API (aunque fetch_with_retry_log debería manejarlas)
                    logger.exception(f"{log_prefix} Unexpected error calling get_linkedin_page_insights for Org {org_urn}: {api_exc}")
                    raw_data = None # Asegurar que raw_data es None

                # --- Transformar y Cargar ---
                # Intentar transformar solo si raw_data no es None (indicando que la llamada API no falló gravemente)
                if raw_data is not None:
                    # transform_and_load_linkedin debe ser capaz de manejar Nones para 'followers' o 'views'
                    logger.info(f"{log_prefix} Transforming and loading LinkedIn data for {org_urn}...")
                    rows_processed = transform_and_load_linkedin(raw_data, org_urn, conn) # Pasar org_urn
                else:
                    # Esto ahora significa que o el URN era inválido (logueado en la API) o ambas llamadas fallaron (logueado en la API)
                    logger.warning(f"{log_prefix} No processable insights data obtained for LinkedIn Org {org_urn}.")

            else:
                # El account_id NO es un URN de organización válido.
                logger.error(f"{log_prefix} Invalid account_id provided for LinkedIn insights task. Expected 'urn:li:organization:...', got: {account_id}. Skipping.")

        elapsed_time = time.time() - start_time

        logger.info(f"{log_prefix} Completed ETL for {platform} - Account: {account_id}. Rows processed: {rows_processed}. Time: {elapsed_time:.2f}s")

        return {"status": "Completed", "platform": platform, "account_id": account_id, "rows_processed": rows_processed, "elapsed_time": elapsed_time}

    except ConnectionError as db_conn_err:
        logger.error(f"{log_prefix} ETL failed - DB Connection Error: {db_conn_err}")
        try:
            # Aumentar countdown para errores de conexión
            self.retry(exc=db_conn_err, countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"{log_prefix} Max retries exceeded for DB Connection Error.")
            return {"status": "Failed", "error": f"DB Connection Error after retries: {db_conn_err}"}
    except psycopg.Error as db_exc:
        logger.exception(f"{log_prefix} ETL task failed - PostgreSQL Error: {db_exc}")
        if conn:
            try:
                conn.rollback() # Intentar rollback
                logger.info(f"{log_prefix} Transaction rolled back due to PostgreSQL error.")
            except Exception as rb_err:
                logger.error(f"{log_prefix} Error during rollback: {rb_err}")
        try:
            self.retry(exc=db_exc)
        except self.MaxRetriesExceededError:
             logger.error(f"{log_prefix} Max retries exceeded for PostgreSQL Error.")
             return {"status": "Failed", "error": f"Max retries exceeded (PostgreSQL Error): {db_exc}"}
    except ValueError as val_err: # Capturar errores de validación (ej. token faltante)
         logger.error(f"{log_prefix} ETL task failed - Validation Error: {val_err}")
         # Normalmente no se reintenta por errores de valor
         return {"status": "Failed", "error": f"Validation Error: {val_err}"}
    except Exception as exc:
        logger.exception(f"{log_prefix} ETL task failed unexpectedly: {exc}")
        try:
            # Reintentar para errores genéricos, podrían ser temporales
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(f"{log_prefix} Max retries exceeded for unexpected error.")
            return {"status": "Failed", "error": f"Max retries exceeded: {exc}"}
    finally:
        if conn:
            # Asegurarse de cerrar la conexión incluso si hubo rollback
            conn.close()
            logger.debug(f"{log_prefix} PostgreSQL connection closed for task.")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def publish_post_task(self, platform, account_id, access_token, content, **kwargs):
    """Celery task to publish content on a social media platform."""
    logger.info(f"[Task ID: {self.request.id}] Starting post publication to {platform} - Account: {account_id}")

    start_time = time.time()
    try:
        result = None

        if platform == "Instagram":
            page_access_token = kwargs.get('page_access_token', access_token)
            ig_user_id = account_id
            image_url = kwargs.get('image_url') # You need to pass this
            if not page_access_token: raise ValueError("Missing page_access_token for Instagram post")
            if not image_url: raise ValueError("Missing image_url for Instagram post") # Assume image required
            result = post_to_instagram(ig_user_id, page_access_token, image_url=image_url, caption=content)
            
        elif platform == "LinkedIn":
            org_urn = account_id
            result = post_to_linkedin_organization(org_urn, access_token, content)

        elapsed_time = time.time() - start_time
        post_id = result.get('id', 'N/A') if result else 'N/A'
        logger.info(f"[Task ID: {self.request.id}] Successfully published to {platform} - Account: {account_id}. Post ID: {post_id}. Time: {elapsed_time:.2f}s")

        return {"status": "Completed", "platform": platform, "account_id": account_id, "post_id": post_id, "elapsed_time": elapsed_time}

    except Exception as exc:
        logger.exception(f"[Task ID: {self.request.id}] Post publication task failed for {platform} - Account: {account_id}. Error: {exc}")
        # self.retry(exc=exc)
        return {"status": "Failed", "platform": platform, "account_id": account_id, "error": str(exc)}


@celery_app.task(name="content_generation_task", bind=True)
def content_generation_task(self, payload_dict: dict, checkpoint: dict = None):
    """
    Tarea Celery que ejecuta el grafo y devuelve el resultado.
    Celery almacenará este valor de retorno en el backend de resultados (Redis).
    """
    logger.info(f"[Task ID: {self.request.id}] LangGraph task started. Resuming: {bool(checkpoint)}")
    
    try:
        # Import the global graph object for Celery/background context
        if not graph:
            logger.error("LangGraph is not initialized. Cannot process content generation request.")
            raise Exception("LangGraph is not initialized.")

        thread_id = str(uuid.uuid4())

        # Si no hay checkpoint, es una ejecución nueva
        if not checkpoint:
            initial_state = {
                **(payload_dict or {}), "token_usage_by_node": {}, "total_tokens": 0, "review_notes": "",
                "revision_cycles": 0, "creative_brief": None, "draft_content": None,
                "refined_content": None, "formatted_output": None, "final_post": None, "human_feedback" : ""
            }
        else:
            # Si hay checkpoint, este ya contiene todo el estado anterior
            initial_state = checkpoint


        callback = TokenUsageCallback(initial_state)

        logger.warning(f"[AI LangGraph] Invoking graph with thread ID {thread_id} and input: {initial_state}")

        # Ejecutar el grafo de forma asíncrona
        final_state = asyncio.run(
            graph.ainvoke(
                initial_state, 
                config={"callbacks": [callback], "configurable": {"thread_id": thread_id}}
            )
        )

        # Si el grafo se interrumpió, `final_state` contiene el checkpoint
        if final_state.get('__interrupt__'):
            logger.info(f"[Task ID: {self.request.id}] Graph interrupted, pending human input.")
            # Actualizamos el estado de la tarea en Celery
            self.update_state(
                state='PENDING_USER_INPUT',
                meta={
                    'draft_content': final_state['extract_final_post']['final_post'],
                    'checkpoint': final_state # Guardamos el checkpoint completo
                }
            )
            # Detenemos la tarea sin marcarla como un error
            raise Ignore()

        result = {
            "final_post": final_state.get("final_post", "Error: No se pudo generar el contenido."),
            "token_usage_per_node": final_state.get("token_usage_by_node"),
            "total_tokens_used": final_state.get("total_tokens")
        }

        logger.info(f"[Task ID: {self.request.id}] LangGraph execution successful. Returning result.")
        
        # Simplemente devuelve el resultado. Celery lo guarda en Redis.
        return result

    except Exception as e:
        logger.exception(f"[Task ID: {self.request.id}] LangGraph task failed: {e}")
        # Deja que la excepción se propague. Celery la capturará y marcará la tarea como FAILURE.
        raise e
