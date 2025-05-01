from src.celery_app import celery_app
from src.core.logger import logger
from src.data_processing import ( transform_and_load_instagram, transform_and_load_linkedin, get_db_connection)
from src.social_apis import (
     get_instagram_insights, get_linkedin_page_insights,
    post_to_instagram, post_to_linkedin_organization
)
from datetime import datetime
import time
import psycopg # Asegurarse que psycopg está importado si se usa aquí


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
            raw_data = {'followers': None, 'views': None} # Inicializar

            if account_id and account_id.startswith("urn:li:organization:"):
                logger.info(f"{log_prefix} Account {account_id} is an Organization. Fetching insights...")

                org_urn = account_id
                start_ts = int(start_date_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                end_ts = int(end_date_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

                try:
                    # Llamar a la función API
                    raw_data = get_linkedin_page_insights(org_urn, access_token, start_ts, end_ts)
                    logger.info(f"{log_prefix} Raw insights data received for Org {org_urn}: {raw_data is not None}")
                except Exception as api_exc:
                     logger.error(f"{log_prefix} Failed to get LinkedIn insights for Org {org_urn}: {api_exc}", exc_info=True)
                     # raw_data seguirá None/vacío
            elif account_id and account_id.startswith("urn:li:person:"):
                 logger.info(f"{log_prefix} Account {account_id} is a Personal Profile. Skipping organizational insights fetch.")
                 # No hacer nada aquí, raw_data se queda {'followers': None, 'views': None}
            else:
                 logger.warning(f"{log_prefix} Unrecognized LinkedIn account URN format: {account_id}. Skipping insights fetch.")

            # --- Transformar y Cargar ---
            if raw_data is not None: # Solo intentar si no hubo error fatal en la obtención
                 # Pasar conexión síncrona
                 rows_processed = transform_and_load_linkedin(raw_data, account_id, conn)
            else:
                 logger.info(f"{log_prefix} No raw data available to transform for {account_id}.")

        elapsed_time = time.time() - start_time

        logger.info(f"{log_prefix} Completed ETL for {platform} - Account: {account_id}. Rows processed: {rows_processed}. Time: {elapsed_time:.2f}s")

        return {"status": "Completed", "platform": platform, "account_id": account_id, "rows_processed": rows_processed, "elapsed_time": elapsed_time}

    except ConnectionError as db_conn_err:
        logger.error(f"{log_prefix} ETL failed - DB Connection Error: {db_conn_err}")
        try: 
            self.retry(exc=db_conn_err, countdown=30)
        except self.MaxRetriesExceededError:
            return {"status": "Failed", "error": f"DB Connection Error: {db_conn_err}"}
    except psycopg.Error as db_exc: # Capturar errores específicos de PostgreSQL
        logger.exception(f"{log_prefix} ETL task failed - PostgreSQL Error: {db_exc}")
        if conn: 
            conn.rollback() # Rollback en error de DB
        try:
            self.retry(exc=db_exc)
        except self.MaxRetriesExceededError: 
            return {"status": "Failed", "error": f"Max retries exceeded (PostgreSQL Error): {db_exc}"}
    except Exception as exc:
        logger.exception(f"{log_prefix} ETL task failed unexpectedly: {exc}")
        try: 
            self.retry(exc=exc)
        except self.MaxRetriesExceededError: 
            return {"status": "Failed", "error": f"Max retries exceeded: {exc}"}
    finally:
        if conn:
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
