import streamlit as st
from typing import Dict, Any
import requests
import time

from src.services import api_client
from src.core.logger import logger
from src.content_generation import render_content_form, render_publication_controls
from src.components.ui_helpers import render_stepper, render_feedback_box

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


def render_generation_form():
    with st.container(border=True):
        st.subheader("Paso 1: Definir publicación")
        st.caption("Completa los campos para que la IA genere un borrador adaptado a tus necesidades.")
        niche, tone, query, link_url, submitted = render_content_form()
        return niche, tone, query, link_url, submitted


def render_polling_ui():
    with st.container(border=True):
        st.subheader("Generando contenido...")
        st.caption("La IA está trabajando en tu publicación. Este proceso puede tardar unos segundos.")
        with st.status("Iniciando generación...", expanded=True) as status:
            st.write("Esperando respuesta del backend...")
            status.update(label="Procesando solicitud", state="running")


def render_review_ui(draft_content: str, checkpoint: str, task_id_for_resume: str):
    with st.container(border=True):
        st.subheader("Paso 2: Revisar y refinar")
        st.caption("Lee el borrador, edítalo si lo deseas y aprueba o pide mejoras. Puedes abortar y empezar de nuevo si no te convence.")
        edited_content = st.text_area(
            "Borrador generado",
            value=draft_content or "",
            height=250,
            key="review_draft_content",
            disabled=False
        )
        st.session_state.draft_content = edited_content
        with st.form("feedback_form"):
            feedback_text = st.text_input("Feedback para la IA (opcional)")
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                approve_button = st.form_submit_button("✅ Aprobar", type="primary", use_container_width=True)
            with col2:
                refine_button = st.form_submit_button("✨ Refinar", use_container_width=True)
            with col3:
                restart_button = st.form_submit_button("🔄 Empezar de Nuevo", use_container_width=True)
            if approve_button:
                try:
                    with st.status("Finalizando publicación..."):
                        response = api_client.resume_content_generation(task_id_for_resume, "aprobar")
                        st.session_state.generation_task_id = response['task_id']
                        del st.session_state.draft_content
                        del st.session_state.checkpoint
                        del st.session_state.task_id_for_resume
                        st.rerun()
                except Exception as e:
                    render_feedback_box(f"Error al aprobar el contenido: {e}", type_="error")
            if refine_button:
                try:
                    with st.status("Enviando feedback a la IA..."):
                        response = api_client.resume_content_generation(task_id_for_resume, feedback_text)
                        st.session_state.generation_task_id = response['task_id']
                        del st.session_state.draft_content
                        del st.session_state.checkpoint
                        del st.session_state.task_id_for_resume
                        st.rerun()
                except Exception as e:
                    render_feedback_box(f"Error al enviar feedback: {e}", type_="error")
            if restart_button:
                for key in ['draft_content', 'checkpoint', 'task_id_for_resume', 'generation_task_id']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()


def render_publish_ui(final_post: str, final_link_url: str, account_name: str, platform: str, account_id: str):
    with st.container(border=True):
        st.subheader("Paso 3: Publicar")
        st.caption("Revisa el contenido final y publícalo en la plataforma seleccionada.")
        edited_final_post = st.text_area(
            "",
            value=final_post or "",
            height=250,
            key="final_post_preview",
            disabled=False
        )
        st.session_state.draft_content = edited_final_post
        
        # Controles de publicación
        render_publication_controls(
            final_post=edited_final_post or "",
            final_link_url=final_link_url or "",
            selected_display_name=account_name,
            active_platform=platform,
            active_account_id=account_id or "",
            api_client_module=api_client
        )
        
        # Botón para guardar para más tarde
        st.divider()
        st.caption("O guarda el post para publicarlo más tarde:")
        if st.button("💾 Guardar para más tarde", type="secondary", use_container_width=True):
            token = api_client._get_current_token()
            if not token:
                st.error("No hay token de autenticación. Por favor, inicia sesión.")
            else:
                try:
                    with st.status("Guardando post..."):
                        # Llamar al endpoint para guardar para más tarde
                        response = requests.post(
                            f"{api_client.FASTAPI_URL}/content/save_for_later",
                            json={
                                "content": edited_final_post or "",
                                "platform": platform,
                                "account_id": account_id,
                                "link_url": final_link_url
                            },
                            headers={"Authorization": f"Bearer {token}"}
                        )
                        response.raise_for_status()
                        post_id = response.json()
                        st.success(f"✅ Post guardado para más tarde (ID: {post_id})")
                        # Limpiar el estado de generación
                        for key in ['draft_content', 'generation_task_id', 'checkpoint', 'task_id_for_resume']:
                            if key in st.session_state:
                                del st.session_state[key]
                        time.sleep(2)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar el post: {e}")
                    logger.error(f"Error saving post for later: {e}")


def render_page(active_context: Dict[str, Any]):
    if not active_context:
        st.error("Error interno: Se intentó renderizar la página sin un contexto de cuenta activo.")
        return

    st.title("✍️ Generación de Contenido")
    account_name = active_context.get("name", "Cuenta desconocida")
    platform = active_context.get("platform", "Plataforma desconocida")
    account_id = str(active_context.get("account_id", ""))

    if 'generation_task_id' in st.session_state and st.session_state.generation_task_id:
        render_stepper(0, ["Generando", "Revisión", "Publicación"])
        task_id = st.session_state.generation_task_id
        try:
            status_data = api_client.get_generation_status(task_id)
            status = status_data.get("status")
            if status == "SUCCESS":
                render_feedback_box("¡Contenido generado con éxito!", type_="success")
                result = status_data.get("result", {})
                st.session_state.draft_content = result.get("final_post")
                del st.session_state.generation_task_id
                st.rerun()
            elif status == "PENDING_USER_INPUT":
                render_feedback_box("Se requiere tu revisión para continuar.", type_="info")
                info = status_data.get("info", {})
                st.session_state.draft_content = info.get("draft_content")
                st.session_state.checkpoint = info.get("checkpoint")
                st.session_state.task_id_for_resume = task_id
                del st.session_state.generation_task_id
                st.rerun()
            elif status == "FAILURE":
                render_feedback_box(f"Error en la generación: {status_data.get('error', 'Error desconocido')}", type_="error")
                del st.session_state.generation_task_id
                st.rerun()
            else:
                render_polling_ui()
                st.info("La IA sigue trabajando en tu contenido...")
                st.rerun()
        except Exception as e:
            render_feedback_box(f"Error al consultar el estado: {e}", type_="error")
            del st.session_state.generation_task_id
            st.rerun()
    elif 'draft_content' in st.session_state and st.session_state.draft_content:
        if 'checkpoint' in st.session_state and st.session_state.checkpoint and 'task_id_for_resume' in st.session_state:
            render_stepper(1, ["Generando", "Revisión", "Publicación"])
            render_review_ui(
                draft_content=st.session_state.draft_content or "",
                checkpoint=st.session_state.checkpoint or "",
                task_id_for_resume=st.session_state.task_id_for_resume or ""
            )
        else:
            render_stepper(2, ["Generando", "Revisión", "Publicación"])
            render_publish_ui(
                final_post=st.session_state.draft_content or "",
                final_link_url=st.session_state.get("draft_link_url", "") or "",
                account_name=account_name,
                platform=platform,
                account_id=account_id or ""
            )
    else:
        render_stepper(0, ["Generando", "Revisión", "Publicación"])
        niche, tone, query, link_url, submitted = render_generation_form()
        if submitted:
            if not query or not niche:
                render_feedback_box("Por favor, completa los campos 'Nicho' y 'Descripción'.", type_="warning")
            else:
                try:
                    with st.status("Enviando tu solicitud a la IA..."):
                        task_id = api_client.start_content_generation(
                            tone=tone, query=query, niche=niche,
                            account_name=account_name, link_url=link_url
                        )
                        st.session_state.generation_task_id = task_id
                        st.session_state.draft_link_url = link_url
                        st.rerun()
                except Exception as e:
                    render_feedback_box(f"Error al iniciar la generación: {e}", type_="error")