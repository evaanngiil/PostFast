from src.celery_app import celery_app
from src.core.logger import logger
from src.data_processing import ( transform_and_load_instagram, transform_and_load_linkedin, get_db_connection)
from src.social_apis import (
     get_instagram_insights, get_linkedin_page_insights,
    post_to_instagram, post_to_linkedin_organization
)
from src.agents.content_agent.callbacks import TokenUsageCallback
from src.dependencies.graph import graph
from src.content_generation import ContentGenerationResult
from src.agents.content_agent.nodes.quality_gate import HumanReviewRequired

from langchain_core.runnables import RunnableConfig
from celery.exceptions import Ignore
from datetime import datetime, timezone
import time
import psycopg
import asyncio
import uuid

def run_graph_sync(input_data: dict, run_config: RunnableConfig):
    """
    Helper function to run the graph synchronously, handling event loop properly.
    """
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                import concurrent.futures
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(graph.ainvoke(input_data, config=run_config))
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                return loop.run_until_complete(graph.ainvoke(input_data, config=run_config))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(graph.ainvoke(input_data, config=run_config))
            finally:
                loop.close()
    except Exception as e:
        logger.error(f"Error in run_graph_sync: {e}")
        raise

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
def content_generation_task(self, payload_dict=None, checkpoint=None):
    """
    Tarea Celery que ejecuta el grafo y devuelve el resultado.
    Celery almacenará este valor de retorno en el backend de resultados (Redis).
    """
    try:
        # Si hay un checkpoint, reanudar desde ahí
        if checkpoint:
            logger.info(f"Resuming task {self.request.id} from checkpoint")
            thread_id = checkpoint.get('thread_id')
            graph_state = checkpoint.get('graph_state')
        else:
            # Nueva ejecución
            logger.info(f"Starting new content generation task {self.request.id}")
            thread_id = str(uuid.uuid4())

            # Transformar payload a estado interno
            if payload_dict is None:
                raise ValueError("payload_dict cannot be None for new task execution")
                
            graph_state = {
                "query": payload_dict["query"],
                "tone": payload_dict["tone"],
                "niche": payload_dict["niche"],
                "account_name": payload_dict["account_name"],
                "link_url": payload_dict.get("link_url"),
                "creative_brief": None,
                "draft_content": None,
                "refined_content": None,
                "final_post": None,
                "review_notes": "",
                "revision_cycles": 0,
                "human_feedback": None,
                "token_usage_by_node": {},
                "total_tokens": 0
            }

        # Configuración del hilo
        thread_config = RunnableConfig(configurable={"thread_id": thread_id})

        # Crear callback para contar tokens
        token_callback = TokenUsageCallback(graph_state)
        run_config = RunnableConfig(callbacks=[token_callback])
        run_config.update(thread_config)

        try:
            if checkpoint:
                # Reanudar desde checkpoint - pasar el estado restaurado, no None
                logger.info(f"[TASK content] Resuming")
                final_state = run_graph_sync(graph_state, run_config)
            else:
                # Nueva ejecución
                final_state = run_graph_sync(graph_state, run_config)

            # Si llegamos aquí, el workflow terminó exitosamente
            result = ContentGenerationResult(
                final_post=final_state.get("final_post", "Error: No se pudo generar el contenido final."),
                token_usage_per_node=token_callback.get_token_usage_by_node(),
                total_tokens_used=token_callback.get_total_tokens()
            )

            logger.info(f"Content generation completed successfully. Task ID: {self.request.id}")
            return result.__dict__


        except HumanReviewRequired as human_review_exc:
            logger.info(f"Human review required. Task ID: {self.request.id}")
            
            # Usar el estado de la excepción
            current_state = human_review_exc.state
            
            checkpoint_data = {
                'thread_id': thread_id,
                'graph_state': current_state
            }
            
            # Extraer el borrador más reciente para mostrar en la UI
            draft_content = (
                current_state.get('final_post') or 
                current_state.get('draft_content', 'Draft not available')
            )

            # Actualizar el estado de la tarea en Celery
            self.update_state(
                state='PENDING_USER_INPUT',
                meta={
                    'status': 'PENDING_USER_INPUT',
                    'checkpoint': checkpoint_data,
                    'draft_content': draft_content # Importante para la UI
                }
            )

            
            raise Ignore()
          
        except Exception as e:
            logger.error(f"An unexpected error occurred in task {self.request.id}: {e}", exc_info=True)
            raise

    except Exception as e:
        logger.exception(f"Error in content generation task {self.request.id}: {e}")
        raise

# This task resumes a suspended LangGraph workflow and injects human feedback.
@celery_app.task(bind=True)
def resume_content_generation_task(self, checkpoint, payload):
    """
    Reanuda una tarea de generación de contenido después del feedback humano.
    """
    try:
        logger.info(f"Resuming task {self.request.id} from checkpoint with feedback.")
        
        # 1. Validar y extraer datos necesarios
        if not checkpoint: raise ValueError("Checkpoint is missing.")
        thread_id = checkpoint.get('thread_id')
        if not thread_id: raise ValueError("Invalid checkpoint: Missing thread_id.")
                
        # Obtener el estado COMPLETO del grafo desde el checkpoint.
        graph_state = checkpoint.get('graph_state')
        if not graph_state:
            raise ValueError("Graph state missing from checkpoint.")

        # Obtener el feedback del payload.
        feedback = payload.get('feedback')
        if not feedback:
            raise ValueError("Feedback is missing in payload.")

        # Actualizar el campo 'human_feedback' DENTRO del diccionario de estado completo.
        graph_state['human_feedback'] = feedback
        
        logger.info(f"Injecting feedback: '{feedback}' into thread {thread_id}")

        # Configurar el grafo para la reanudación.
        token_callback = TokenUsageCallback(graph_state)
        run_config = RunnableConfig(
            configurable={"thread_id": thread_id},
            callbacks=[token_callback]
        )
        
        # Optimización para el caso "aprobar" (sigue siendo válida)
        if feedback.strip().lower() == 'aprobar':
            logger.info("Approval feedback received. Finalizing task.")
            # ... (esta parte no necesita cambios)
            final_post = graph_state.get('final_post', 'Contenido no encontrado.')
            result = ContentGenerationResult(final_post, graph_state.get('token_usage_by_node', {}), graph_state.get('total_tokens', 0))
            return result.__dict__

        # Ejecutar el grafo pasando el estado COMPLETO y ACTUALIZADO.
        # Esto pasará la validación de `InputState` porque `graph_state` ya contiene `query`, etc.
        try:
            final_state = run_graph_sync(graph_state, run_config)

            result = ContentGenerationResult(
                final_post=final_state.get("final_post", "Error: No se pudo generar el contenido final."),
                token_usage_per_node=token_callback.get_token_usage_by_node(),
                total_tokens_used=token_callback.get_total_tokens()
            )
            logger.info(f"Content generation RESUMED and COMPLETED. Task ID: {self.request.id}")
            return result.__dict__

        except HumanReviewRequired as human_review_exc:
            logger.info(f"Pausing AGAIN for review after refinement. Task ID: {self.request.id}.")
            current_state = human_review_exc.state
            new_checkpoint = {'thread_id': thread_id, 'graph_state': current_state}
            draft_content = current_state.get('final_post') or current_state.get('draft_content')

            self.update_state(
                state='PENDING_USER_INPUT',
                meta={'status': 'PENDING_USER_INPUT', 'checkpoint': new_checkpoint, 'draft_content': draft_content}
            )
            raise Ignore()

    except Exception as e:
        logger.exception(f"FATAL error resuming task {self.request.id}: {e}")
        raise