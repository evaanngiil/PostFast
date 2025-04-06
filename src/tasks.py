from src.celery_app import celery_app
from src.core.logger import logger
from src.data_processing import ( transform_and_load_instagram, transform_and_load_linkedin, get_db_connection)
from src.social_apis import (
     get_instagram_insights, get_linkedin_page_insights,
    post_to_instagram, post_to_linkedin_organization
)
from datetime import datetime
import time

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5) # bind=True to access the task instance
def run_etl_pipeline_task(self, platform, account_id, access_token, start_date_str, end_date_str, **kwargs):
    """Celery task to run the ETL pipeline in the background."""
    logger.info(f"[Task ID: {self.request.id}] Starting ETL for {platform} - Account: {account_id} | Period: {start_date_str} to {end_date_str}")
    start_time = time.time()
    rows_processed = 0
    conn = get_db_connection()
    try:
        start_date_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date_dt = datetime.strptime(end_date_str, '%Y-%m-%d')

        if platform == "Facebook":
            # NOTE: FB Insights requires page access token
            page_access_token = kwargs.get('page_access_token', access_token) # Use page access token if passed
            if not page_access_token: raise ValueError("Missing page_access_token for Facebook ETL")
            raw_data = get_facebook_page_insights(account_id, page_access_token, start_date_str, end_date_str)
            if raw_data:
                rows_processed = transform_and_load_facebook(raw_data, account_id, conn)
        elif platform == "Instagram":
            # NOTE: IG Insights requires page access token and IG User ID
            page_access_token = kwargs.get('page_access_token', access_token)
            ig_user_id = account_id # Assume that account_id is the IG User ID
            if not page_access_token: raise ValueError("Missing page_access_token for Instagram ETL")
            raw_data = get_instagram_insights(ig_user_id, page_access_token, start_date_str, end_date_str)
            if raw_data:
                rows_processed = transform_and_load_instagram(raw_data, ig_user_id, conn)
        elif platform == "LinkedIn":
            # NOTE: LinkedIn requires organization URN and user token
            org_urn = account_id
            start_ts = int(start_date_dt.timestamp() * 1000)
            end_ts = int(end_date_dt.timestamp() * 1000)
            raw_data = get_linkedin_page_insights(org_urn, access_token, start_ts, end_ts)
            if raw_data:
                 rows_processed = transform_and_load_linkedin(raw_data, org_urn, conn)

        elapsed_time = time.time() - start_time
        logger.info(f"[Task ID: {self.request.id}] Completed ETL for {platform} - Account: {account_id}. Rows processed: {rows_processed}. Time: {elapsed_time:.2f}s")
        return {"status": "Completed", "platform": platform, "account_id": account_id, "rows_processed": rows_processed, "elapsed_time": elapsed_time}

    except Exception as exc:
         logger.exception(f"[Task ID: {self.request.id}] ETL task failed for {platform} - Account: {account_id}. Error: {exc}")
         # Automatically retry if possible (defined in @celery_app.task)
         # self.retry(exc=exc) # Celery does this automatically if max_retries is not exceeded
         # Return failure status for polling
         return {"status": "Failed", "platform": platform, "account_id": account_id, "error": str(exc)}
    finally:
        if conn: conn.close()

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def publish_post_task(self, platform, account_id, access_token, content, **kwargs):
    """Celery task to publish content on a social media platform."""
    logger.info(f"[Task ID: {self.request.id}] Starting post publication to {platform} - Account: {account_id}")
    start_time = time.time()
    try:
        result = None
        if platform == "Facebook":
            page_access_token = kwargs.get('page_access_token', access_token)
            if not page_access_token: raise ValueError("Missing page_access_token for Facebook post")
            result = post_to_facebook_page(account_id, page_access_token, content)
        elif platform == "Instagram":
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
