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


# def render_page(context: Dict[str, Any]):    
#     if 'generation_task_id' in st.session_state:
#         if 'generation_task_info' in st.session_state and st.session_state['generation_task_info'] is not None:
#             render_feedback_form()
#         else:
#             handle_polling()
#         return
        
#     niche, tone, query_description, link_url, submitted = render_content_form()
    
#     if submitted:
#         try:
#             task_id = api_client.start_content_generation(
#                 tone=tone, query=query_description, niche=niche,
#                 account_name=context['name'], link_url=link_url
#             )
#             st.session_state['generation_task_id'] = task_id
#             st.session_state['polling_attempts'] = 0
#             st.rerun()
#         except requests.exceptions.RequestException as e:
#             st.error(f"Failed to start generation task: {e}")

#     if 'draft_content' in st.session_state:
#         draft = st.session_state['draft_content']
#         st.markdown("### Draft Content")
#         st.write(draft)
        
#          # Le pasamos el api_client a la función de renderizado de controles
#         render_publication_controls(
#             draft, link_url, context['name'], context['platform'],
#             context['account_id'], api_client # Pasamos el módulo
#         )

def render_page(active_context: Dict[str, Any]):
    """
    Renders the entire content generation page with stateful logic
    for polling and handling user feedback.
    """
    st.title("✍️ Content Generation")

    # Extraer datos del contexto activo
    account_name = active_context.get("name", "Unknown Account")
    platform = active_context.get("platform", "Unknown Platform")
    account_id = active_context.get("account_id", None)

    # --- CICLO DE VIDA DE LA GENERACIÓN DE CONTENIDO ---

    # CASO 1: Hay una tarea de generación en curso. Hacemos polling.
    if 'generation_task_id' in st.session_state and st.session_state.generation_task_id:
        task_id = st.session_state.generation_task_id
        
        with st.spinner(f"AI is working on it... (Task ID: {task_id[-8:]})"):
            while True:
                try:
                    status_data = api_client.get_generation_status(task_id)
                    status = status_data.get("status")

                    if status == "SUCCESS":
                        st.success("Content generated successfully!")
                        result = status_data.get("result", {})
                        st.session_state.draft_content = result.get("final_post")
                        # Limpiamos el ID de la tarea para salir del bucle de polling
                        del st.session_state.generation_task_id
                        st.rerun() # Volver a ejecutar para mostrar el borrador
                        break

                    elif status == "PENDING_USER_INPUT":
                        st.info("Your feedback is required to continue.")
                        info = status_data.get("info", {})
                        st.session_state.draft_content = info.get("draft_content")
                        st.session_state.checkpoint = info.get("checkpoint")
                        # Guardamos el ID de la tarea original para la reanudación
                        st.session_state.task_id_for_resume = task_id
                        del st.session_state.generation_task_id
                        st.rerun()
                        break

                    elif status == "FAILURE":
                        st.error(f"Content generation failed. Error: {status_data.get('error', 'Unknown error')}")
                        del st.session_state.generation_task_id
                        st.rerun()
                        break
                    
                    # Si sigue en PENDING u otro estado intermedio, esperamos y volvemos a consultar
                    time.sleep(2)

                except Exception as e:
                    st.error(f"Error checking task status: {e}")
                    del st.session_state.generation_task_id
                    st.rerun()
                    break

    # CASO 2: Hay un borrador esperando feedback o publicación.
    elif 'draft_content' in st.session_state and st.session_state.draft_content:
        st.subheader("2. Review and Publish")
        
        # Mostrar el borrador en un área de texto para que sea editable
        edited_content = st.text_area(
            "📝 Generated Draft", 
            value=st.session_state.draft_content, 
            height=250
        )
        st.session_state.draft_content = edited_content # Guardar cambios en tiempo real

        # Si tenemos un checkpoint, significa que estamos esperando feedback
        if 'checkpoint' in st.session_state and st.session_state.checkpoint:
            st.info("The AI has prepared a draft. You can approve it or provide feedback for refinement.")
            with st.form("feedback_form"):
                feedback_text = st.text_input("Your feedback (e.g., 'make it shorter', 'add a question')")
                
                col1, col2 = st.columns(2)
                with col1:
                    approve_button = st.form_submit_button("✅ Looks Good, Approve!", use_container_width=True)
                with col2:
                    refine_button = st.form_submit_button("✨ Refine with Feedback", use_container_width=True)

                if approve_button:
                    try:
                        with st.spinner("Finalizing content..."):
                            original_task_id = st.session_state.task_id_for_resume
                            # Llamamos a la API con el feedback especial "aprobar"
                            response = api_client.resume_content_generation(original_task_id, "aprobar")
                            
                            # Guardamos el NUEVO task_id para hacer polling
                            st.session_state.generation_task_id = response['task_id']

                            # Limpiamos el estado viejo para forzar el polling
                            del st.session_state.draft_content
                            del st.session_state.checkpoint
                            del st.session_state.task_id_for_resume
                            st.rerun()
                    except Exception as e:
                        st.error(f"Failed to approve content: {e}")

                if refine_button:
                    try:
                        with st.spinner("Sending your feedback to the AI..."):
                            # Usamos el ID de la tarea original para la reanudación
                            original_task_id = st.session_state.task_id_for_resume
                            # La API de reanudación devuelve un NUEVO task_id
                            response = api_client.resume_content_generation(original_task_id, feedback_text)
                            # Actualizamos el ID de la tarea en sesión para empezar a hacer polling de la NUEVA tarea
                            st.session_state.generation_task_id = response['task_id']

                            # Limpiamos el estado antiguo
                            del st.session_state.draft_content
                            del st.session_state.checkpoint
                            del st.session_state.task_id_for_resume
                            st.rerun()

                    except Exception as e:
                        st.error(f"Failed to submit feedback: {e}")
        
        # Si no hay checkpoint, mostramos los controles de publicación
        else:
            final_link_url = st.session_state.get("draft_link_url", "")
            render_publication_controls(
                final_post=st.session_state.draft_content,
                final_link_url=final_link_url,
                selected_display_name=account_name,
                active_platform=platform,
                active_account_id=account_id,
                api_client_module=api_client
            )

    # CASO 3: Estado inicial. Mostramos el formulario de generación.
    else:
        niche, tone, query, link_url, submitted = render_content_form()
        if submitted:
            if not query or not niche:
                st.error("Please fill in both 'Niche' and 'Description' fields.")
            else:
                try:
                    with st.spinner("Sending your request to the AI..."):
                        # Iniciamos la tarea de generación
                        task_id = api_client.start_content_generation(
                            tone=tone, query=query, niche=niche,
                            account_name=account_name, link_url=link_url
                        )
                        # Guardamos el ID de la tarea y el link para usarlos después
                        st.session_state.generation_task_id = task_id
                        st.session_state.draft_link_url = link_url
                        st.rerun() # Re-ejecutar para entrar en el modo de polling
                except Exception as e:
                    st.error(f"Failed to start content generation: {e}")