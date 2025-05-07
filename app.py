# app.py

import pandas as pd
import streamlit as st
from PIL import Image

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
        verify_session_on_load,
        process_auth_params,
        display_auth_status,
        load_user_accounts,
        display_account_selector # Asumimos que esta función se modificó
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

st.set_page_config(
    page_title="AIPost", 
    layout="wide", 
)

fastapi_client = requests.Session()

# --- Initialization and Session Verification ---
try:
    initialize_session_state()
    setup_database()

    session_was_valid = verify_session_on_load()
    processed_new_login = False
    if not session_was_valid:
        processed_new_login = process_auth_params()

    is_connected_now = st.session_state.get("li_connected")
    logger.info(f"Initialization complete. Session valid: {session_was_valid}, New login processed: {processed_new_login}, Currently connected: {is_connected_now}")

    accounts_loaded_or_refreshed = False
    if is_connected_now:
        # Siempre intentar cargar/refrescar si no están o si es un nuevo login/verificación
        # Asumimos que load_user_accounts devuelve True si cargó algo nuevo o diferente
        if load_user_accounts("LinkedIn"):
             accounts_loaded_or_refreshed = True
             logger.info("LinkedIn accounts (including organizations) loaded/refreshed.")
             # Guardar una copia plana para el selector si es necesario por la implementación de display_account_selector
             # Esto depende de cómo implementes display_account_selector
             # Ejemplo: flatten_accounts_for_selector()

    # Rerun si hubo cambios significativos para refrescar UI
    # CUIDADO con bucles de rerun
    if processed_new_login or accounts_loaded_or_refreshed:
         logger.debug(f"Rerunning after new login ({processed_new_login}) or account load/refresh ({accounts_loaded_or_refreshed}).")
         # st.rerun() # Descomentar con precaución

except Exception as init_err:
    st.error(f"Error during application initialization: {init_err}")
    logger.critical(f"Initialization Error: {init_err}", exc_info=True)
    st.stop()

logger.info("Streamlit App Script Execution Start/Reload")

# --- Sidebar ---
with st.sidebar:
    st.title("🚀 AIPost")
    display_auth_status(sidebar=True)
    st.divider()

    # --- Selector de Cuentas ---
    # Asumimos que display_account_selector ahora:
    # 1. Muestra la jerarquía Persona -> Orgs
    # 2. Guarda el *diccionario completo* del item seleccionado en st.session_state.selected_account
    # 3. Devuelve ese mismo diccionario
    selected_account_data = display_account_selector(sidebar=True) # Esta función debe ser modificada!

    st.divider()
    selected_tab = st.radio("Navigation", ["Analytics", "Content Generation", "Scheduling"], key="main_nav")

# --- Procesar cuenta seleccionada ---
active_platform = None
active_account_id = None # ID/URN a USAR en las llamadas API (será el de la ORG si se selecciona una org)
active_account_type = None # 'person' o 'organization'
user_access_token = None
selected_display_name = "N/A" # Nombre a mostrar en la UI

if selected_account_data and isinstance(selected_account_data, dict):
    active_platform = selected_account_data.get('platform')
    # Usamos el URN como identificador principal para las APIs
    active_account_id = selected_account_data.get('urn')
    active_account_type = selected_account_data.get('type') # IMPORTANTE: 'person' o 'organization'
    selected_display_name = selected_account_data.get('name', active_account_id) # Nombre para mostrar

    if active_platform == "LinkedIn":
        user_access_token = st.session_state.get("li_token_data", {}).get("access_token")

    if user_access_token and active_account_id and active_account_type:
        logger.info(f"Active Context Set - Platform: {active_platform}, Selected: {selected_display_name} ({active_account_id}), Type: {active_account_type}, User Token: Yes")
    else:
        logger.warning(f"Active Context Problem - Platform: {active_platform}, Account Selected: {bool(selected_account_data)}, ID: {active_account_id}, Type: {active_account_type}, Token Missing: {not user_access_token}")
        # Resetear si falta información clave
        selected_account_data = None
        active_account_id = None
        active_account_type = None


# --- Helper para añadir cabecera de autenticación ---
def get_auth_headers():
    """Obtiene el token de acceso del usuario y devuelve la cabecera de autorización."""
    access_token = None
    if active_platform == "LinkedIn":
        access_token = st.session_state.get("li_token_data", {}).get("access_token")

    if access_token:
        return {'Authorization': f'Bearer {access_token}'}
    else:
        logger.error(f"Cannot get auth headers: Access token not found for platform {active_platform}")
        return None

# --- Analytics Tab ---
if selected_tab == "Analytics":
    # Usar el nombre para mostrar
    st.header(f"📊 Analytics Dashboard: {selected_display_name if selected_account_data else 'Select an Account'}")

    if not selected_account_data:
        st.info("Please select an account or organization in the sidebar to see analytics.")
    elif not user_access_token:
         st.error(f"Cannot display analytics: User access token for {active_platform} is missing.")
    # --- Solo permitir fetch/display si es una ORGANIZACIÓN ---
    elif active_account_type != "organization":
         st.warning(f"Analytics are only available for LinkedIn Organization pages. Please select an organization from the sidebar.")
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
            st.write(" ")
            # El botón se muestra, pero la lógica interna usa active_account_id (que es el URN de la org)
            if st.button("🔄 Fetch Data", key="fetch_data_button", help="Starts data extraction for the selected organization page."):
                auth_headers = get_auth_headers()
                if not auth_headers:
                     st.error("Cannot fetch data: User token not available.")
                else:
                    etl_endpoint = f"{FASTAPI_URL}/analytics/trigger_etl"
                    # *** USA EL ID DE LA ORGANIZACIÓN SELECCIONADA ***
                    payload = {
                        "platform": active_platform,
                        "account_id": active_account_id, # <--- URN de la ORGANIZACIÓN
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    }
                    logger.info(f"Triggering ETL for Organization URN: {active_account_id}") # Log para confirmar
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
                             st.info(f"Extraction started for {selected_display_name} (Task ID: {st.session_state['etl_task_id']})...")
                             st.rerun()
                        else:
                             st.error("Failed to start extraction task: No Task ID received.")
                             logger.error(f"No task_id in response from /analytics/trigger_etl: {task_info}")

                    except requests.exceptions.RequestException as e:
                        logger.error(f"Failed to trigger ETL task via API for {active_account_id}: {e}", exc_info=True)
                        error_detail = "Authentication error (401)" if e.response and e.response.status_code == 401 else (e.response.text if e.response else str(e))
                        st.error(f"Error starting extraction: {error_detail}")
                    except Exception as e:
                         logger.exception(f"Error processing ETL trigger for {active_account_id}")
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
                                        time.sleep(1) 
                                        st.rerun()
                                        break
                                    elif task_status == "FAILURE":
                                        error_msg = result.get('error', 'Unknown error'); traceback_info = result.get('traceback', '')
                                        status_ctx.update(label="Extraction Failed!", state="error", expanded=True)
                                        st.error(f"Extraction failed: {error_msg}")
                                        logger.error(f"ETL Task {task_id} failed. Error: {error_msg}\nTraceback:\n{traceback_info}")

                                        del st.session_state['etl_task_id'] 
                                        break
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
                         with status_placeholder.container(): 
                            st.warning(f"Could not get final status for task {task_id} after timeout.")
                         if 'etl_task_id' in st.session_state: 
                            del st.session_state['etl_task_id']

        # --- Fin de la lógica de polling ---

        # --- Mostrar KPIs y Gráficas ---
        kpi_metrics_map = {
            "LinkedIn": ("follower_total", "page_views"), # Asumiendo que tienes page_views
        }
        timeseries_metrics_map = {
            "LinkedIn": ["page_views", "follower_total", "follower_growth"], # Asumiendo que tienes page_views
        }

        platform_kpis = kpi_metrics_map.get(active_platform, [])
        platform_timeseries = timeseries_metrics_map.get(active_platform, [])

        latest_kpis = {}
        df_timeseries = pd.DataFrame()

        try:
             # Estas funciones usarán el active_account_id (URN de la org)
             logger.debug(f"Fetching DB data for Org URN: {active_account_id}")
             latest_kpis = get_latest_kpis(active_platform, active_account_id, tuple(platform_kpis))
             df_timeseries = get_metrics_timeseries(active_platform, active_account_id, platform_timeseries, start_date, end_date)
        except Exception as db_err:
            st.error(f"Error fetching analytics data from database for {active_account_id}: {db_err}")
            logger.error(f"Error fetching analytics from DB for {active_account_id}: {db_err}", exc_info=True)

        st.subheader("🚀 Recent KPIs")
        if latest_kpis:
            num_kpis = len(latest_kpis); cols = st.columns(num_kpis or 1)
            i = 0
            friendly_names = { "follower_total": "Seguidores (LI)", "page_views": "Vistas Pág. (LI)"}
            for metric, value in latest_kpis.items():
                 if i < len(cols):
                     with cols[i]: st.metric(label=friendly_names.get(metric, metric), value=f"{value:,}" if isinstance(value, (int, float)) else value)
                     i += 1
        else: 
            st.info("No recent KPIs found. Try fetching data.")
        st.divider()
        
         # Show Graphs
        st.subheader("📈 Main Trends")
        if not df_timeseries.empty:
            logger.debug(f"Timeseries DataFrame for {active_account_id}:\n{df_timeseries.head()}")
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
    st.header("✍️ Content Generator and Publisher")

    if not selected_account_data:
         st.warning("Select an account or organization in the sidebar to publish.")
    elif not user_access_token:
         st.error(f"Cannot generate/publish: User access token for {active_platform} is missing.")
    # --- MODIFICACIÓN: Solo permitir si es una ORGANIZACIÓN ---
    # O podrías permitir publicar al perfil de la persona si active_account_type == "person"
    # Por ahora, lo restringimos a organizaciones según el requerimiento implícito.
    elif active_account_type != "organization":
         st.warning(f"Content publishing is currently enabled only for LinkedIn Organization pages. Please select an organization from the sidebar.")
    else:
        # El nombre y plataforma ya reflejan la organización seleccionada
        st.info(f"Publishing on: **{selected_display_name} ({active_platform} Organization)**")

        with st.form("content_generation_form"):
             st.subheader("1. Define your Publication")
             niche = st.text_input("Niche / Target Audience")
             tone = st.selectbox("Message Tone", ["Professional", "Informal", "Inspirational", "Funny", "Informative"])
             description = st.text_area("Describe briefly what you want to publish", height=100)
             link_url_input = st.text_input("Link URL (Optional)", key="content_link_url")
             submitted_generate = st.form_submit_button("✨ Generate Draft Content")

             if submitted_generate:
                  with st.spinner("Generating content..."): time.sleep(1)
                  draft_content = f"Draft ({tone}) for {selected_display_name}:\n\n{description}\nNiche: {niche}."
                  if link_url_input: draft_content += f"\nLink: {link_url_input}"
                  st.session_state['draft_content'] = draft_content
                  st.session_state['draft_link_url'] = link_url_input

        # Validate and Publish/Schedule Area
        if 'draft_content' in st.session_state:
             st.subheader("2. Validate and Publish/Schedule")
             final_content = st.text_area("Edit content:", value=st.session_state.get('draft_content', ''), height=150, key="final_content_area")
             final_link_url = st.text_input("Final Link URL:", value=st.session_state.get('draft_link_url', ''), key="final_link_url_area")
             publish_now = st.button("✅ Publish Now", key="publish_now_btn")
             schedule_mode = st.toggle("📅 Schedule for later", key="schedule_toggle")
             scheduled_dt_input = None
             if schedule_mode:
                  now_plus_1h = datetime.now(timezone.utc) + timedelta(hours=1)
                  scheduled_dt_input = st.date_input("Publication Date (UTC)", value=now_plus_1h, key="schedule_datetime")
             publish_schedule = st.button("🚀 Confirm Schedule", key="schedule_confirm_btn", disabled=not schedule_mode)

             if publish_now or publish_schedule:
                  auth_headers = get_auth_headers()
                  if not auth_headers:
                       st.error("Cannot publish/schedule: User token not available.")
                  else:
                    schedule_time_iso = None
                    action = "publish_now"
                    if publish_schedule and scheduled_dt_input:
                        # CORRECCIÓN: Combinar fecha y hora si usas datetime picker, o solo fecha si es date_input
                        # Asumiendo date_input por ahora, usar medianoche UTC
                        schedule_time_iso = datetime.combine(scheduled_dt_input, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat(timespec='seconds') # Formato ISO con Z implícito por UTC
                        action = "schedule"
                    elif publish_schedule and not scheduled_dt_input:
                         st.warning("Please select a date to schedule.")
                         st.stop() # Detener ejecución aquí para evitar llamada API

                    schedule_endpoint = f"{FASTAPI_URL}/content/schedule_post"
                    # *** USA EL ID DE LA ORGANIZACIÓN SELECCIONADA ***
                    payload = {
                        "platform": active_platform,
                        "account_id": active_account_id, # <--- URN de la ORGANIZACIÓN
                        "content": final_content,
                        "scheduled_time_str": schedule_time_iso, # None si es publish_now
                        "link_url": final_link_url if final_link_url else None
                        # Añadir link_title si tu backend lo usa para LinkedIn
                    }
                    logger.info(f"Triggering post task ({action}) for Organization URN: {active_account_id}") # Log para confirmar

                    try:
                          with st.spinner(f"{'Scheduling' if action == 'schedule' else 'Publishing'} to {selected_display_name}..."):
                              response = fastapi_client.post(
                                  schedule_endpoint,
                                  json={k: v for k, v in payload.items() if v is not None},
                                  headers=auth_headers
                                )

                              response.raise_for_status()
                              task_info = response.json()
                              task_id = task_info.get("task_id")
                              if task_id:
                                  st.success(f"{'Scheduled' if action == 'schedule' else 'Publishing task started'} for {selected_display_name}! (Task ID: {task_id})")
                                  logger.info(f"Post task triggered ({action}) for {active_account_id}. Task ID: {task_id}")
                                  if 'draft_content' in st.session_state: del st.session_state['draft_content']
                                  if 'draft_link_url' in st.session_state: del st.session_state['draft_link_url']
                                  time.sleep(1); st.rerun()
                              else:
                                   st.error(f"Failed to start {action} task: No Task ID received.")
                                   logger.error(f"No task_id in response from /content/schedule_post for {active_account_id}: {task_info}")

                    except requests.exceptions.RequestException as e:
                         logger.error(f"Failed to trigger post task ({action}) via API for {active_account_id}: {e}", exc_info=True)
                         error_detail = "Authentication error (401)" if e.response and e.response.status_code == 401 else (e.response.text if e.response else str(e))
                         st.error(f"Error during {'scheduling' if action == 'schedule' else 'publishing'}: {error_detail}")
                    except Exception as e:
                         logger.exception(f"Error processing post trigger ({action}) for {active_account_id}")
                         st.error(f"Unexpected error: {e}")


elif selected_tab == "Scheduling":
    st.header("🗓️ Scheduled Posts")
    st.info("View scheduled posts (future implementation).")
    # Si aquí se hicieran llamadas API para obtener el estado de los posts,
    # necesitarían usar get_auth_headers() y fastapi_client con esos headers.


st.sidebar.divider()
st.sidebar.caption(f"AIPost v0.4 (Token Auth) | FastAPI: {FASTAPI_URL}")