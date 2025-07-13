import streamlit as st
from typing import Dict, Any
import requests
import time

from src.services import api_client
from src.core.logger import logger
from src.content_generation import render_content_form, render_publication_controls

def handle_polling(max_attempts=30, delay=3):
    """Gestiona la lógica de polling para obtener el resultado de la tarea."""
    task_id = st.session_state.get('generation_task_id')
    if not task_id:
        return

    st.session_state.setdefault('polling_attempts', 0)
    st.session_state['polling_attempts'] += 1

    if st.session_state['polling_attempts'] > max_attempts:
        st.error("Generation timed out. Please try again.")
        del st.session_state['generation_task_id']
        del st.session_state['polling_attempts']
        st.rerun()

    with st.spinner(f"🧠 The AI is thinking... (Attempt {st.session_state['polling_attempts']}/{max_attempts})"):
        try:
            status_data = api_client.get_generation_status(task_id)
            status = status_data.get("status")
            logger.warning(f"Polling status: {status} for task ID: {task_id}")        
    
            if status == "PENDING_USER_INPUT":
                st.success("🤖 The first draft is ready for your review!")
                st.session_state['generation_task_info'] = status_data.get('info')
                del st.session_state['polling_attempts']
                st.rerun()

            elif status == "SUCCESS":
                st.success("✨ Content generated successfully!")
                result = status_data.get("result", {})
                st.session_state['draft_content'] = result.get("final_post")
                
                # Mostrar el uso de tokens
                tokens_used = result.get("total_tokens_used", 0)
                st.info(f"💡 Total tokens used for this generation: {tokens_used}")

                # Limpiar y salir del modo polling
                del st.session_state['generation_task_id']
                del st.session_state['polling_attempts']
                st.rerun()

            elif status == "FAILURE":
                st.error(f"Content generation failed: {status_data.get('error', 'Unknown error')}")
                del st.session_state['generation_task_id']
                del st.session_state['polling_attempts']
                st.rerun()
            
            else: # PENDING u otro estado
                time.sleep(delay)
                st.rerun()

        except requests.exceptions.RequestException as e:
            st.error(f"Error checking status: {e}")
            del st.session_state['generation_task_id']
            del st.session_state['polling_attempts']
            st.rerun()


def render_feedback_form():
    """Muestra el borrador y los controles para que el usuario dé su feedback."""
    st.subheader("2. Human Review: Refine or Approve")
    
    task_info = st.session_state.get('generation_task_info', {})
    draft_content = task_info.get('draft_content', 'Loading draft...')
    task_id = st.session_state.get('generation_task_id')

    st.text_area("Generated Draft:", value=draft_content, height=250, disabled=True)
    
    st.write("Provide feedback for refinement, or leave blank and click 'Approve' to finish.")
    feedback = st.text_input("Your Feedback:", key="human_feedback_input")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Submit Feedback & Refine", use_container_width=True):
            if not feedback.strip():
                st.warning("Please provide feedback to refine the post.")
            elif task_id:
                api_client.resume_content_generation(task_id, feedback)
                st.session_state['generation_task_info'] = None # Volver a modo polling
                st.rerun()

    with col2:
        if st.button("✅ Approve & Finalize", type="primary", use_container_width=True):
            if task_id:
                api_client.resume_content_generation(task_id, "aprobar")
                st.session_state['generation_task_info'] = None # Volver a modo polling
                st.rerun()


def render_page(context: Dict[str, Any]):    
    if 'generation_task_id' in st.session_state:
        if 'generation_task_info' in st.session_state and st.session_state['generation_task_info'] is not None:
            render_feedback_form()
        else:
            handle_polling()
        return
        
    niche, tone, query_description, link_url, submitted = render_content_form()
    
    if submitted:
        try:
            task_id = api_client.start_content_generation(
                tone=tone, query=query_description, niche=niche,
                account_name=context['name'], link_url=link_url
            )
            st.session_state['generation_task_id'] = task_id
            st.session_state['polling_attempts'] = 0
            st.rerun()
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to start generation task: {e}")

    if 'draft_content' in st.session_state:
        draft = st.session_state['draft_content']
        st.markdown("### Draft Content")
        st.write(draft)
        
         # Le pasamos el api_client a la función de renderizado de controles
        render_publication_controls(
            draft, link_url, context['name'], context['platform'],
            context['account_id'], api_client # Pasamos el módulo
        )

