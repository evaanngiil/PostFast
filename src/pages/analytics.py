import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
import plotly.express as px
import plotly.graph_objects as go
import requests
import time
from typing import Dict, Any

from src.core.logger import logger
from src.services import api_client
from src.data_processing import get_metrics_timeseries, get_latest_kpis

# --- Helper functions for this page ---

def _handle_etl_trigger(context: Dict[str, Any], start_date, end_date):
    """Handles the 'Fetch Data' button click and API call."""
    try:
        task_info = api_client.trigger_etl(
            platform=context['platform'],
            account_id=context['account_id'],
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        task_id = task_info.get('task_id')
        if task_id:
            st.session_state['etl_task_id'] = task_id
            st.info(f"Extraction started for {context['name']} (Task ID: {task_id})...")
            st.rerun()
        else:
            st.error("Failed to start extraction task: No Task ID received.")
            logger.error(f"No task_id in response from /analytics/trigger_etl: {task_info}")
    except (requests.exceptions.RequestException, ConnectionRefusedError) as e:
        error_detail = "Authentication error" if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401 else str(e)
        st.error(f"Error starting extraction: {error_detail}")
        logger.error(f"Failed to trigger ETL task for {context['account_id']}: {e}", exc_info=True)
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        logger.exception(f"Error processing ETL trigger for {context['account_id']}")

def _poll_etl_status(context: Dict[str, Any]):
    """Polls for the status of an active ETL task."""
    task_id = st.session_state.get('etl_task_id')
    if not task_id: return

    status_placeholder = st.empty()
    with st.spinner(f"Waiting for extraction result (Task: {task_id})..."):
        for _ in range(24):  # Max 2 minutes of polling (24 * 5s)
            try:
                task_status_data = api_client.get_task_status(task_id, context['platform'])
                task_status = task_status_data.get("status")

                with status_placeholder.container():
                    with st.status(f"ETL Task ({task_id}): {task_status}", expanded=True) as status_ctx:
                        result = task_status_data.get("result", {})
                        if task_status == "SUCCESS":
                            status_ctx.update(label="Extraction Completed!", state="complete", expanded=False)
                            st.success(f"Processed: {result.get('rows_processed', 'N/A')} rows.")
                            del st.session_state['etl_task_id']
                            time.sleep(1); st.rerun()
                            return
                        elif task_status == "FAILURE":
                            error_msg = result.get('error', 'Unknown error')
                            status_ctx.update(label="Extraction Failed!", state="error", expanded=True)
                            st.error(f"Extraction failed: {error_msg}")
                            logger.error(f"ETL Task {task_id} failed: {result}")
                            del st.session_state['etl_task_id']
                            return
                        elif task_status in ["PENDING", "STARTED", "RETRY"]:
                            status_ctx.update(label=f"ETL Task ({task_id}): {task_status}...", state="running")
                            time.sleep(5)
                        else:
                            status_ctx.update(label=f"ETL Task ({task_id}): Status '{task_status}'", state="error")
                            logger.warning(f"Unexpected task status for {task_id}: {task_status}")
                            del st.session_state['etl_task_id']
                            return
            except (requests.exceptions.RequestException, ConnectionRefusedError) as e:
                logger.error(f"Polling error for task {task_id}: {e}")
                st.error("Connection error while checking status. Please wait.")
                time.sleep(10)
            except Exception as e:
                logger.exception(f"Unexpected error in task polling {task_id}")
                st.error(f"Unexpected error querying status: {e}")
                del st.session_state['etl_task_id']
                return
        
        logger.warning(f"Polling timed out for task {task_id}.")
        st.warning(f"Could not get task status after timeout. Please check back later.")
        if 'etl_task_id' in st.session_state: del st.session_state['etl_task_id']


def _display_data(context: Dict[str, Any], start_date, end_date):
    """Fetches and displays KPIs and charts from the database."""
    platform = context['platform']
    account_id = context['account_id']
    
    kpi_metrics = ("follower_total", "page_views")
    ts_metrics = ["page_views", "follower_total", "follower_growth"]

    try:
        latest_kpis = get_latest_kpis(platform, account_id, kpi_metrics)
        df_timeseries = get_metrics_timeseries(platform, account_id, ts_metrics, start_date, end_date)
    except Exception as db_err:
        st.error(f"Error fetching analytics data from database: {db_err}")
        logger.error(f"DB Error for {account_id}: {db_err}", exc_info=True)
        return

    st.subheader("🚀 Recent KPIs")
    if latest_kpis:
        cols = st.columns(len(latest_kpis) or 1)
        friendly_names = {"follower_total": "Total Followers", "page_views": "Page Views"}
        for i, (metric, value) in enumerate(latest_kpis.items()):
            cols[i].metric(label=friendly_names.get(metric, metric), value=f"{value:,}")
    else:
        st.info("No recent KPIs found. Try fetching new data.")
    
    st.divider()
    
    st.subheader("📈 Main Trends")
    if not df_timeseries.empty:
        fig = px.line(df_timeseries, x=df_timeseries.index, y=ts_metrics, title=f"Daily Trends for {context['name']}")
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("See Raw Data"):
            st.dataframe(df_timeseries.style.format("{:,.0f}", na_rep='-'))
    else:
        st.info("No time series data found for the selected range.")

def render_page(context: Dict[str, Any]):
    """Renders the Analytics Dashboard page."""
    st.header(f"📊 Analytics Dashboard: {context.get('name', 'Select an Account')}")

    # Pre-condition checks
    if not context.get('data'):
        st.info("Please select an account or organization in the sidebar to see analytics.")
        return
    if not context.get('token'):
        st.error(f"Access token for {context['platform']} is missing. Please reconnect.")
        return
    if context.get('account_type') != "organization":
        st.warning("Analytics are only available for LinkedIn Organization pages.")
        return

    # --- Date and Update Controls ---
    col1, col2 = st.columns([3, 1])
    with col1:
        today = datetime.now(timezone.utc).date()
        date_range = st.date_input("Select Date Range", (today - timedelta(days=29), today), max_value=today)
        start_date, end_date = date_range if len(date_range) == 2 else (None, None)
    with col2:
        st.write(" ")
        if st.button("🔄 Fetch Data", use_container_width=True, help="Extract new data for the selected page."):
            if start_date and end_date:
                _handle_etl_trigger(context, start_date, end_date)

    # --- Polling and Data Display ---
    _poll_etl_status(context)
    if 'etl_task_id' not in st.session_state and start_date and end_date:
        _display_data(context, start_date, end_date)