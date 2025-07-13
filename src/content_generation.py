from datetime import datetime, timezone
import requests
from typing import Dict, Any
import streamlit as st
from dataclasses import dataclass

from src.core.logger import logger

# --- UI Component: Form ---
def render_content_form() -> tuple[str, str, str, str, bool]:
    """Renders the content generation form and returns input values."""
    with st.form("content_generation_form"):
        st.subheader("1. Define your Publication")
        niche = st.text_input("Niche / Target Audience", help="E.g., 'Software developers interested in AI'")
        tone = st.selectbox("Message Tone", ["Professional", "Informal", "Inspirational", "Funny", "Informative"])
        # Cambiamos el nombre de la variable para que sea más claro
        query_description = st.text_area("Describe what you want to publish", height=100, help="E.g., 'A post announcing our new LangGraph integration'")
        link_url = st.text_input("Link URL (Optional)", key="content_link_url")
        submitted = st.form_submit_button("✨ Generate Draft Content")
        
        return niche, tone, query_description, link_url, submitted


@dataclass
class ContentGenerationResult:
    final_post: str
    token_usage_per_node: Dict[str, int]
    total_tokens_used: int

def render_publication_controls(
    final_post: str,
    final_link_url: str,
    selected_display_name: str,
    active_platform: str,
    active_account_id: str,
    api_client_module: Any 
) -> None:
    """Renders and handles publication controls."""
    publish_now = st.button("✅ Publish Now", key="publish_now_btn", use_container_width=True)
    schedule_mode = st.toggle("📅 Schedule for later", key="schedule_toggle")
    scheduled_time = None
    
    if schedule_mode:
        col1, col2 = st.columns(2)
        now_utc = datetime.now(timezone.utc)
        with col1:
            scheduled_date = st.date_input("Date (UTC)", value=now_utc, min_value=now_utc.date(), key="schedule_date")
        with col2:
            scheduled_time_input = st.time_input("Time (UTC)", value=now_utc, key="schedule_time")
        
        if scheduled_date and scheduled_time_input:
            scheduled_time = datetime.combine(scheduled_date, scheduled_time_input).replace(tzinfo=timezone.utc)

    publish_schedule = st.button("🚀 Confirm Schedule", key="schedule_confirm_btn", disabled=not schedule_mode or not scheduled_time, use_container_width=True)

    action_triggered = publish_now or (publish_schedule and scheduled_time)
    if action_triggered:
        # Validar que el tiempo programado no sea en el pasado
        if schedule_mode and scheduled_time and scheduled_time < datetime.now(timezone.utc):
            st.error("Scheduled time cannot be in the past.")
            return

        try:
            action_string = 'Scheduling' if schedule_mode else 'Publishing'
            with st.spinner(f"{action_string} to {selected_display_name}..."):
                result = api_client_module.schedule_or_publish_post(
                    active_platform,
                    active_account_id,
                    final_post,  # Cambiado de final_content a final_post
                    scheduled_time if publish_schedule else None,
                    final_link_url
                )
                
                if task_id := result.get("task_id"):
                    st.success(f"Post {action_string.lower()} task started successfully! (Task ID: {task_id})")
                    # Limpiar el borrador de la sesión para un nuevo ciclo
                    for key in ['draft_content', 'draft_link_url']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
                else:
                    st.error("Failed to start task: No Task ID received from the API.")
                    
        except requests.exceptions.RequestException as e:
            error_detail = "Authentication error" if getattr(e.response, 'status_code', None) == 401 else str(e)
            st.error(f"Error during {action_string.lower()}: {error_detail}")
            logger.error(f"API Error during publication: {e}", exc_info=True)