from src.celery_app import celery_app
from src.core.logger import logger
from src.social_apis import (
    post_to_instagram, post_to_linkedin_organization
)
from src.agents.content_agent.callbacks import TokenUsageCallback
from src.dependencies.graph import graph
from src.content_generation import ContentGenerationResult
from src.agents.content_agent.nodes.quality_gate import HumanReviewRequired
from src.services.api_client import create_post

from langchain_core.runnables import RunnableConfig
from celery.exceptions import Ignore
from datetime import datetime, timezone
import time
## Removed psycopg dependency (migrated to Supabase)
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
            # Guardar post como publicado
            create_post(
                content=content,
                status="published",
                platform=platform,
                account_id=account_id,
                published_time=datetime.now(timezone.utc),
                image_url=image_url
            )
            
        elif platform == "LinkedIn":
            org_urn = account_id
            result = post_to_linkedin_organization(org_urn, access_token, content)
            # Guardar post como publicado
            create_post(
                content=content,
                status="published",
                platform=platform,
                account_id=account_id,
                published_time=datetime.now(timezone.utc)
            )

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

        # Asegurar que el estado tenga todos los campos necesarios
        required_fields = {
            "query": "",
            "tone": "",
            "niche": "",
            "account_name": "",
            "link_url": None,
            "creative_brief": None,
            "draft_content": None,
            "refined_content": None,
            "formatted_output": None,
            "final_post": None,
            "review_notes": "",
            "revision_cycles": 0,
            "human_feedback": None,
            "token_usage_by_node": {},
            "total_tokens": 0
        }
        
        # Inicializar campos faltantes
        for field, default_value in required_fields.items():
            if field not in graph_state:
                graph_state[field] = default_value
                logger.warning(f"Missing field '{field}' in graph state, initialized with default value")

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