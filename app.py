# app.py

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
import plotly.express as px
import plotly.graph_objects as go
import requests
import time
import json

# --- Imports ---
try: 
    from src.core.constants import FASTAPI_URL
except ImportError: 
    FASTAPI_URL = "http://localhost:8000" 
    print(f"WARN: Default FASTAPI_URL: {FASTAPI_URL}")

from src.core.logger import logger

try:
    from src.auth import (
        initialize_session_state,
        verify_session_on_load, # <-- NUEVO: Para verificar en cada carga
        process_auth_params,    # <-- Para procesar params de URL si no hay sesión verificada
        display_auth_status,
        load_user_accounts,     # <-- Para cargar cuentas después de verificar/conectar
        display_account_selector
    )
except ImportError as e: 
    st.error(f"Fatal Import Error (auth): {e}") 
    logger.critical(f"Import Error (auth): {e}", exc_info=True); st.stop()

try: 
    from src.data_processing import setup_database, get_metrics_timeseries, get_latest_kpis
except ImportError as e: 
    st.error(f"Fatal Import Error (data): {e}") 
    logger.critical(f"Import Error (data): {e}", exc_info=True); st.stop()

# --- End Imports ---

# Cliente HTTP para hacer llamadas API a FastAPI
# Usaremos este cliente para añadir el token Bearer
fastapi_client = requests.Session() # Cliente global para llamadas API

# --- Streamlit Page Configuration ---
st.set_page_config(layout="wide", page_title="AIPost")

# --- Initialization and Session Verification ---
try:
    initialize_session_state() # Asegura que session_state existe con defaults
    setup_database()           # Configura DuckDB

    # 1. Intentar verificar sesión existente (usando token almacenado)
    session_was_valid = verify_session_on_load()

    # 2. Si no se verificó sesión, intentar procesar params de URL (nuevo login)
    processed_new_login = False
    if not session_was_valid:
        processed_new_login = process_auth_params()

    # 3. Determinar si estamos conectados ahora
    is_connected_now = st.session_state.get("fb_connected") or st.session_state.get("li_connected")
    logger.info(f"Initialization complete. Session valid: {session_was_valid}, New login processed: {processed_new_login}, Currently connected: {is_connected_now}")

    # 4. Cargar cuentas SI estamos conectados y aún no están cargadas
    accounts_loaded_this_run = False
    if is_connected_now:
        if st.session_state.get("fb_connected") and not st.session_state.user_accounts.get("Facebook"):
            logger.debug("Attempting to load Facebook accounts post-verification/login...")
            if load_user_accounts("Facebook"): accounts_loaded_this_run = True
        if st.session_state.get("li_connected") and not st.session_state.user_accounts.get("LinkedIn"):
            logger.debug("Attempting to load LinkedIn accounts post-verification/login...")
            if load_user_accounts("LinkedIn"): accounts_loaded_this_run = True

    # Si acabamos de cargar cuentas (o procesar un nuevo login), un rerun puede ayudar
    # a asegurar que la UI (especialmente el selector) esté actualizada.
    if processed_new_login or accounts_loaded_this_run:
         logger.debug(f"Rerunning after new login ({processed_new_login}) or account load ({accounts_loaded_this_run}).")
         # Usar rerun con precaución, podría causar bucles si no se maneja bien el estado
         # st.rerun() # Comentar si causa problemas

except Exception as init_err:
    st.error(f"Error during application initialization: {init_err}")
    logger.critical(f"Initialization Error: {init_err}", exc_info=True)
    st.stop()

logger.info("Streamlit App Script Execution Start/Reload") # Log para ver cada ejecución

# --- Sidebar ---
with st.sidebar:
    st.title("🚀 AIPost")
    # Muestra estado (incluyendo user info/pic), botones connect/disconnect
    display_auth_status(sidebar=True)

    st.divider() # Separador antes del selector

    # Selector de cuenta activa (debería funcionar ahora si las cuentas se cargaron)
    selected_account_data = display_account_selector(sidebar=True)

    st.divider()
    selected_tab = st.radio("Navigation", ["Analytics", "Content Generation", "Scheduling"], key="main_nav")

active_platform = None; active_account_id = None; user_access_token = None
account_specific_token = None; selected_account_name = "N/A"

if selected_account_data and isinstance(selected_account_data, dict):
    active_platform = selected_account_data.get('platform')
    active_account_id = selected_account_data.get('id')
    selected_account_name = selected_account_data.get('name', active_account_id)
    if active_platform == "Facebook":
        user_access_token = st.session_state.get("fb_token_data", {}).get("access_token")
        account_specific_token = selected_account_data.get('access_token') # FB Page token
    elif active_platform == "LinkedIn":
        user_access_token = st.session_state.get("li_token_data", {}).get("access_token")
    if user_access_token: 
        logger.debug(f"Active Context Set - Platform: {active_platform}, Account: {selected_account_name} ({active_account_id}), User Token: Yes")
    else: 
        logger.warning(f"Active Context NOT Set - Platform: {active_platform}, Account Selected: {bool(selected_account_data)}, User Token Missing!")

# --- Helper para añadir cabecera de autenticación ---
def get_auth_headers():
    """Obtiene el token de acceso del usuario y devuelve la cabecera de autorización."""
    access_token = None
    if active_platform == "Facebook":
        access_token = st.session_state.get("fb_token_data", {}).get("access_token")
    elif active_platform == "LinkedIn":
        access_token = st.session_state.get("li_token_data", {}).get("access_token")

    if access_token:
        return {'Authorization': f'Bearer {access_token}'}
    else:
        logger.error(f"Cannot get auth headers: Access token not found for platform {active_platform}")
        return None

# --- Analytics Tab ---
if selected_tab == "Analytics":
    st.header(f"📊 Analytics Dashboard: {selected_account_name if selected_account_data else 'Select an Account'}")

    if not selected_account_data:
        st.info("Please select an account/page in the sidebar to see analytics.")
    elif not user_access_token: # Verificar si tenemos el token necesario
         st.error(f"Cannot display analytics: User access token for {active_platform} is missing.")
    else:
        # --- Date and Update Controls ---
        col1, col2 = st.columns([3, 1])
        with col1:
            today = datetime.now(timezone.utc).date()
            default_start = today - timedelta(days=29)
            date_range = st.date_input(
                "Select Date Range",
                (default_start, today),
                max_value=today, key="analytics_date_range"
            )
            start_date, end_date = date_range if len(date_range) == 2 else (default_start, today)
        with col2:
            st.write(" ") # Spacer
            if st.button("🔄 Fetch Data", key="fetch_data_button", help="Starts data extraction for the selected period."):
                auth_headers = get_auth_headers() # Obtener cabecera con token Bearer
                if not auth_headers:
                     st.error("Cannot fetch data: User token not available.")
                else:
                    etl_endpoint = f"{FASTAPI_URL}/analytics/trigger_etl" # Ruta del router
                    # Payload ya NO necesita incluir el token_data, se envía en header
                    payload = {
                        "platform": active_platform,
                        "account_id": active_account_id,
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d'),
                        # Enviar token de página FB si existe y es necesario para el endpoint
                        "page_access_token": account_specific_token if active_platform == "Facebook" else None
                    }
                    try:
                        response = fastapi_client.post(
                            etl_endpoint,
                            json={k: v for k, v in payload.items() if v is not None},
                            headers=auth_headers
                        )
                        response.raise_for_status()
                        task_info = response.json()
                        st.session_state['etl_task_id'] = task_info.get('task_id')
                        if st.session_state['etl_task_id']:
                             st.info(f"Extraction started (Task ID: {st.session_state['etl_task_id']})...")
                             st.rerun()
                        else:
                             st.error("Failed to start extraction task: No Task ID received.")
                             logger.error(f"No task_id in response from /analytics/trigger_etl: {task_info}")

                    except requests.exceptions.RequestException as e:
                        logger.error(f"Failed to trigger ETL task via API: {e}", exc_info=True)
                        error_detail = "Authentication error (401)" if e.response and e.response.status_code == 401 else (e.response.text if e.response else str(e))
                        st.error(f"Error starting extraction: {error_detail}")
                    except Exception as e:
                         logger.exception("Error processing ETL trigger")
                         st.error(f"Unexpected error: {e}")

        # --- Polling for ETL task status ---
        if 'etl_task_id' in st.session_state and st.session_state['etl_task_id']:
            task_id = st.session_state['etl_task_id']
            status_endpoint = f"{FASTAPI_URL}/analytics/tasks/status/{task_id}" # Ruta del router
            status_placeholder = st.empty()
            auth_headers = get_auth_headers() # Necesario para pedir el status también

            if not auth_headers:
                 st.error("Cannot check task status: User token not available.")
                 del st.session_state['etl_task_id'] # Limpiar task id si no podemos verificar
            else:
                 with st.spinner(f"Waiting for extraction result (Task: {task_id})..."):
                    poll_count = 0; max_polls = 24
                    while poll_count < max_polls:
                        poll_count += 1
                        try:
                            # --- CAMBIO: Añadir headers ---
                            response = fastapi_client.get(status_endpoint, headers=auth_headers)
                            if response.status_code == 404:
                                logger.warning(f"Task {task_id} not found (404). Maybe pending registration or expired?")
                                time.sleep(5); continue

                            response.raise_for_status() # Check for other errors (like 401 if token expired)
                            task_status_data = response.json()
                            task_status = task_status_data.get("status")

                            with status_placeholder.container():
                                with st.status(f"ETL Task ({task_id}): {task_status}", expanded=True) as status_ctx:
                                    result = task_status_data.get("result", {})
                                    if task_status == "SUCCESS":
                                        status_ctx.update(label="Extraction Completed!", state="complete", expanded=False)
                                        st.success(f"Extraction successful. Rows processed: {result.get('rows_processed', 0)}")
                                        del st.session_state['etl_task_id']
                                        time.sleep(1); st.rerun(); break
                                    elif task_status == "FAILURE":
                                        error_msg = result.get('error', 'Unknown error'); traceback_info = result.get('traceback', '')
                                        status_ctx.update(label="Extraction Failed!", state="error", expanded=True)
                                        st.error(f"Extraction failed: {error_msg}")
                                        logger.error(f"ETL Task {task_id} failed. Error: {error_msg}\nTraceback:\n{traceback_info}")
                                        del st.session_state['etl_task_id']; break
                                    elif task_status in ["PENDING", "STARTED", "RETRY"]:
                                        status_ctx.update(label=f"ETL Task ({task_id}): {task_status}...", state="running", expanded=True)
                                        time.sleep(5) # Wait before next poll
                                    else:
                                        status_ctx.update(label=f"ETL Task ({task_id}): Unknown Status '{task_status}'", state="error", expanded=True)
                                        logger.warning(f"Unexpected task status for {task_id}: {task_status}")
                                        del st.session_state['etl_task_id']; break
                        except requests.exceptions.RequestException as e:
                             logger.error(f"Error querying task status {task_id}: {e}")
                             with status_placeholder.container():
                                  error_msg = "Authentication error" if e.response and e.response.status_code == 401 else "Connection error"
                                  st.error(f"Error querying task status: {error_msg}.")
                             if e.response and e.response.status_code == 401: # Si es auth error, parar polling
                                  del st.session_state['etl_task_id']; break
                             time.sleep(10)
                             if poll_count > 5: logger.error(f"Stopping polling for task {task_id} due to persistent connection errors."); del st.session_state['etl_task_id']; break
                        except Exception as e:
                             logger.exception(f"Unexpected error in task polling {task_id}")
                             with status_placeholder.container(): st.error(f"Unexpected error querying status: {e}")
                             del st.session_state['etl_task_id']; break
                    else: # Max polls reached
                         logger.warning(f"Polling timed out for task {task_id} after {max_polls} attempts.")
                         with status_placeholder.container(): st.warning(f"Could not get final status for task {task_id} after timeout.")
                         if 'etl_task_id' in st.session_state: del st.session_state['etl_task_id']

        # --- Fin de la lógica de polling ---

        # --- Mostrar KPIs y Gráficas ---
        kpi_metrics_map = {
            "Facebook": ("page_fans", "page_impressions", "page_post_engagements"),
            "LinkedIn": ("follower_total", "page_views"), # Asumiendo que tienes page_views
        }
        timeseries_metrics_map = {
            "Facebook": ["page_impressions", "page_post_engagements", "engagement_rate", "page_fans", "follower_growth"],
            "LinkedIn": ["page_views", "follower_total", "follower_growth"], # Asumiendo que tienes page_views
        }

        platform_kpis = kpi_metrics_map.get(active_platform, [])
        platform_timeseries = timeseries_metrics_map.get(active_platform, [])

        latest_kpis = {}
        df_timeseries = pd.DataFrame()

        try:
            latest_kpis = get_latest_kpis(active_platform, active_account_id, tuple(platform_kpis))
            df_timeseries = get_metrics_timeseries(active_platform, active_account_id, platform_timeseries, start_date, end_date)
        except Exception as db_err:
            st.error(f"Error fetching analytics data from database: {db_err}")
            logger.error(f"Error fetching analytics from DB: {db_err}", exc_info=True)

        st.subheader("🚀 Recent KPIs")
        if latest_kpis:
            num_kpis = len(latest_kpis); cols = st.columns(num_kpis or 1)
            i = 0
            friendly_names = {"page_fans": "Fans (FB)", "follower_total": "Seguidores (LI)", "page_impressions": "Impr. (FB)", "page_post_engagements": "Interac. (FB)", "page_views": "Vistas Pág. (LI)"}
            for metric, value in latest_kpis.items():
                 if i < len(cols):
                     with cols[i]: st.metric(label=friendly_names.get(metric, metric), value=f"{value:,}" if isinstance(value, (int, float)) else value)
                     i += 1
        else: st.info("No recent KPIs found. Try fetching data.")
        st.divider()
        
         # Show Graphs
        st.subheader("📈 Main Trends")
        if not df_timeseries.empty:
            # Ensure timeseries metrics requested exist in the dataframe columns
            metrics_to_plot = [m for m in platform_timeseries if m in df_timeseries.columns and m not in ['follower_total', 'page_fans']]

            if metrics_to_plot:
                try:
                    fig_trends = px.line(df_timeseries, x=df_timeseries.index, y=metrics_to_plot,
                                         labels={"value": "Value", "metric_date": "Date", "variable": "Metric"},
                                         title=f"Daily Trends ({selected_account_name})")
                    fig_trends.update_layout(hovermode="x unified")
                    st.plotly_chart(fig_trends, use_container_width=True)
                except Exception as plot_err:
                     st.error(f"Error generating trends chart: {plot_err}")
                     logger.error(f"Plotly Error (Trends): {plot_err}", exc_info=True)
            else:
                st.info("No daily trends data available to plot for the selected metrics.")

            # Follower Growth Graph
            follower_metric = 'follower_total' if 'follower_total' in df_timeseries.columns else ('page_fans' if 'page_fans' in df_timeseries.columns else None)
            if follower_metric:
                 st.subheader("👥 Follower Growth")
                 try:
                     fig_followers = go.Figure()
                     fig_followers.add_trace(go.Scatter(x=df_timeseries.index, y=df_timeseries[follower_metric], mode='lines+markers', name='Total', yaxis='y1'))
                     if 'follower_growth' in df_timeseries.columns:
                         fig_followers.add_trace(go.Bar(x=df_timeseries.index, y=df_timeseries['follower_growth'], name='Daily Growth', yaxis='y2'))
                     fig_followers.update_layout(title=f"Follower Evolution ({selected_account_name})", xaxis_title="Date", yaxis=dict(title="Total", side='left'), yaxis2=dict(title="Daily Growth", overlaying='y', side='right', showgrid=False), hovermode="x unified", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
                     st.plotly_chart(fig_followers, use_container_width=True)
                 except Exception as plot_err:
                     st.error(f"Error generating follower chart: {plot_err}")
                     logger.error(f"Plotly Error (Followers): {plot_err}", exc_info=True)


            with st.expander("See Table Data"):
                 st.dataframe(df_timeseries.style.format("{:,.0f}", na_rep='-')) # Apply formatting
        else:
             st.info("No time series data found. Try fetching data.")


elif selected_tab == "Content Generation":
    st.header("✍️ Content Generator and Publisher (FB & LI)")

    if not selected_account_data:
         st.warning("Select an account/page in the sidebar to publish.")
    elif not user_access_token: # Verificar token
         st.error(f"Cannot generate/publish: User access token for {active_platform} is missing.")
    else:
        st.info(f"Publishing on: **{selected_account_name} ({active_platform})**")

        with st.form("content_generation_form"):
             st.subheader("1. Define your Publication")
             # ... inputs ...
             niche = st.text_input("Niche / Target Audience")
             tone = st.selectbox("Message Tone", ["Professional", "Informal", "Inspirational", "Funny", "Informative"])
             description = st.text_area("Describe briefly what you want to publish", height=100)
             link_url_input = st.text_input("Link URL (Optional)", key="content_link_url")
             submitted_generate = st.form_submit_button("✨ Generate Draft (AI)")
             if submitted_generate:
                  # Placeholder LangChain call
                  with st.spinner("Generating content..."): time.sleep(1)
                  draft_content = f"Draft ({tone}) for {active_platform}:\n\n{description}\nNiche: {niche}."
                  if link_url_input: draft_content += f"\nLink: {link_url_input}"
                  st.session_state['draft_content'] = draft_content
                  st.session_state['draft_link_url'] = link_url_input # Guardar link también

        # Validate and Publish/Schedule Area
        if 'draft_content' in st.session_state:
             st.subheader("2. Validate and Publish/Schedule")
             final_content = st.text_area("Edit content:", value=st.session_state.get('draft_content', ''), height=150, key="final_content_area")
             final_link_url = st.text_input("Final Link URL:", value=st.session_state.get('draft_link_url', ''), key="final_link_url_area") # Editar link también

             publish_now = st.button("✅ Publish Now", key="publish_now_btn")
             # ... (schedule logic sin cambios) ...
             schedule_mode = st.toggle("📅 Schedule for later", key="schedule_toggle")
             scheduled_dt_input = None
             if schedule_mode:
                  now_plus_1h = datetime.now(timezone.utc) + timedelta(hours=1)
                  scheduled_dt_input = st.datetime_input("Publication Date (UTC)", value=now_plus_1h, key="schedule_datetime")
             publish_schedule = st.button("🚀 Confirm Schedule", key="schedule_confirm_btn", disabled=not schedule_mode)


             if publish_now or publish_schedule:
                  auth_headers = get_auth_headers() # Obtener token Bearer
                  if not auth_headers:
                       st.error("Cannot publish/schedule: User token not available.")
                  else:
                    schedule_time_iso = None
                    action = "publish_now"
                    if publish_schedule and scheduled_dt_input:
                        schedule_time_iso = scheduled_dt_input.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                        action = "schedule"
                    elif publish_schedule and not scheduled_dt_input:
                         st.warning("Please select a date and time to schedule.")
                         st.stop()

                    schedule_endpoint = f"{FASTAPI_URL}/content/schedule_post" # Ruta del router
                    # Payload ya NO necesita token_data
                    payload = {
                        "platform": active_platform,
                        "account_id": active_account_id,
                        "content": final_content,
                        "scheduled_time_str": schedule_time_iso,
                        # Enviar token de página FB si existe y el endpoint lo espera
                        "page_access_token": account_specific_token if active_platform == "Facebook" else None,
                        "link_url": final_link_url if final_link_url else None
                        # Añadir otros campos si el endpoint los necesita (ej. title para LI)
                    }

                    try:
                          with st.spinner(f"{'Scheduling' if action == 'schedule' else 'Publishing'}..."):
                              response = fastapi_client.post(
                                  schedule_endpoint,
                                  json={k: v for k, v in payload.items() if v is not None},
                                  headers=auth_headers
                                )
                              response.raise_for_status()
                              task_info = response.json()
                              task_id = task_info.get("task_id")
                              if task_id:
                                  st.success(f"{'Scheduled' if action == 'schedule' else 'Publishing task started'}! (Task ID: {task_id})")
                                  logger.info(f"Post task triggered ({action}). Task ID: {task_id}")
                                  # Clean draft state
                                  if 'draft_content' in st.session_state: del st.session_state['draft_content']
                                  if 'draft_link_url' in st.session_state: del st.session_state['draft_link_url']
                                  time.sleep(1); st.rerun()
                              else:
                                   st.error("Failed to start task: No Task ID received.")
                                   logger.error(f"No task_id in response from /content/schedule_post: {task_info}")

                    except requests.exceptions.RequestException as e:
                         logger.error(f"Failed to trigger post task ({action}) via API: {e}", exc_info=True)
                         error_detail = "Authentication error (401)" if e.response and e.response.status_code == 401 else (e.response.text if e.response else str(e))
                         st.error(f"Error during {'scheduling' if action == 'schedule' else 'publishing'}: {error_detail}")
                    except Exception as e:
                         logger.exception(f"Error processing post trigger ({action})")
                         st.error(f"Unexpected error: {e}")

elif selected_tab == "Scheduling":
    st.header("🗓️ Scheduled Posts")
    st.info("View scheduled posts (future implementation).")
    # Si aquí se hicieran llamadas API para obtener el estado de los posts,
    # necesitarían usar get_auth_headers() y fastapi_client con esos headers.


# --- Footer (Sin cambios) ---
st.sidebar.divider()
st.sidebar.caption(f"AIPost v0.4 (Token Auth) | FastAPI: {FASTAPI_URL}")