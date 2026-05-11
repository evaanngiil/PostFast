import streamlit as st
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import requests
import time

from src.services import api_client
from src.core.logger import logger
from src.components.ui_helpers import render_stepper, render_feedback_box


@dataclass
class ContentGenerationResult:
    """
    Resultado de la generación de contenido a través del grafo multi-agente.
    """
    def __init__(self, final_post, token_usage_per_node, total_tokens_used):
        self.final_post = final_post
        self.token_usage_per_node = token_usage_per_node
        self.total_tokens_used = total_tokens_used


def handle_polling(max_attempts=30, delay=3):
    """
    Gestiona la lógica de polling para obtener el resultado asíncrono de la tarea.

    :param max_attempts: Número máximo de intentos antes de abortar.
    :param delay: Tiempo de espera (en segundos) entre intentos.
    :returns: None
    """
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

    with st.spinner(f"\U0001f9e0 The AI is thinking... (Attempt {st.session_state['polling_attempts']}/{max_attempts})"):
        try:
            status_data = api_client.get_generation_status(task_id)
            status = status_data.get("status")
            logger.warning(f"Polling status: {status} for task ID: {task_id}")        

            if status == "PENDING_USER_INPUT":
                st.success("\U0001f916 The first draft is ready for your review!")
                st.session_state['generation_task_info'] = status_data.get('info')
                del st.session_state['polling_attempts']
                st.rerun()

            elif status == "SUCCESS":
                st.success("\u2728 Content generated successfully!")
                result = status_data.get("result", {})
                st.session_state['draft_content'] = result.get("final_post")

                tokens_used = result.get("total_tokens_used", 0)
                st.info(f"\U0001f4a1 Total tokens used for this generation: {tokens_used}")

                del st.session_state['generation_task_id']
                del st.session_state['polling_attempts']
                st.rerun()

            elif status == "FAILURE":
                st.error(f"Content generation failed: {status_data.get('error', 'Unknown error')}")
                del st.session_state['generation_task_id']
                del st.session_state['polling_attempts']
                st.rerun()

                st.rerun()

            else:
                st.rerun()

        except requests.exceptions.RequestException as e:
            st.error(f"Error checking status: {e}")
            del st.session_state['generation_task_id']
            del st.session_state['polling_attempts']
            st.rerun()


def render_content_form() -> tuple[str, str, str, str, bool]:
    """
    Renderiza el formulario de configuración para la generación de contenido.

    :returns: Una tupla con (nicho, tono, descripción, URL de enlace, estado del submit).
    """
    with st.form("content_generation_form"):
        niche = st.text_input("Niche / Target Audience", help="E.g., 'Software developers interested in AI'")
        tone = st.selectbox("Message Tone", ["Professional", "Informal", "Inspirational", "Funny", "Informative"])
        query_description = st.text_area("Describe what you want to publish", height=100, help="E.g., 'A post announcing our new LangGraph integration'")
        link_url = st.text_input("Link URL (Optional)", key="content_link_url")
        submitted = st.form_submit_button("\u2728 Generate Draft Content")

        return niche, tone, query_description, link_url, submitted


def render_publication_controls(
    final_post: str,
    final_link_url: str,
    selected_display_name: str,
    active_platform: str,
    active_account_id: str,
    api_client_module: Any 
) -> None:
    """
    Renderiza y gestiona los controles para publicación inmediata o programada.

    :param final_post: Contenido final del post.
    :param final_link_url: URL adicional (opcional) a incluir.
    :param selected_display_name: Nombre legible de la cuenta de destino.
    :param active_platform: Plataforma destino (ej. LinkedIn).
    :param active_account_id: Identificador de la cuenta seleccionada.
    :param api_client_module: Módulo o servicio del cliente API.
    :returns: None
    """
    publish_now = st.button("\u2705 Publish Now", key="publish_now_btn", use_container_width=True)
    schedule_mode = st.toggle("\U0001f4c5 Schedule for later", key="schedule_toggle")
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

    publish_schedule = st.button("\U0001f680 Confirm Schedule", key="schedule_confirm_btn", disabled=not schedule_mode or not scheduled_time, use_container_width=True)

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
                    final_post,
                    scheduled_time if publish_schedule else None,
                    final_link_url
                )

                if task_id := result.get("task_id"):
                    st.success(f"Post {action_string.lower()} task started successfully! (Task ID: {task_id})")
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


def render_generation_form():
    with st.container(border=True):
        st.subheader("Paso 1: Definir publicacion")
        st.caption("Completa los campos para que la IA genere un borrador adaptado a tus necesidades.")
        niche, tone, query, link_url, submitted = render_content_form()
        return niche, tone, query, link_url, submitted


def render_polling_ui():
    with st.container(border=True):
        st.subheader("Generando contenido...")
        st.caption("La IA esta trabajando en tu publicacion. Este proceso puede tardar unos segundos.")
        with st.status("Iniciando generacion...", expanded=True) as status:
            st.write("Esperando respuesta del backend...")
            status.update(label="Procesando solicitud", state="running")


def render_review_ui(draft_content: str, checkpoint: str, task_id_for_resume: str):
    with st.container(border=True):
        st.subheader("Paso 2: Revisar y refinar")
        st.caption("Lee el borrador, editalo si lo deseas y aprueba o pide mejoras. Puedes abortar y empezar de nuevo si no te convence.")
        review_cycle = st.session_state.get("review_cycle", 0)
        draft_key = f"review_draft_content_{review_cycle}"
        edited_content = st.text_area(
            "Borrador generado",
            value=draft_content or "",
            height=250,
            key=draft_key,
            disabled=False
        )
        st.session_state.draft_content = edited_content
        feedback_key = f"feedback_text_input_{review_cycle}"
        with st.form(f"feedback_form_{review_cycle}"):
            feedback_text = st.text_input("Feedback para la IA (opcional)", key=feedback_key)
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                approve_button = st.form_submit_button("\u2705 Aprobar", type="primary", use_container_width=True)
            with col2:
                refine_button = st.form_submit_button("\u2728 Refinar", use_container_width=True)
            with col3:
                restart_button = st.form_submit_button("\U0001f504 Empezar de Nuevo", use_container_width=True)
            if approve_button:
                try:
                    with st.status("Finalizando publicacion..."):
                        response = api_client.resume_content_generation(task_id_for_resume, "aprobar")
                        st.session_state.generation_task_id = response['task_id']
                        old_cycle = st.session_state.get("review_cycle", 0)
                        st.session_state["review_cycle"] = old_cycle + 1
                        for key in ['draft_content', 'checkpoint',
                                    'task_id_for_resume',
                                    f'feedback_text_input_{old_cycle}',
                                    f'review_draft_content_{old_cycle}']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                except Exception as e:
                    render_feedback_box(f"Error al aprobar el contenido: {e}", type_="error")
            if refine_button:
                try:
                    with st.status("Enviando feedback a la IA..."):
                        response = api_client.resume_content_generation(task_id_for_resume, feedback_text)
                        st.session_state.generation_task_id = response['task_id']
                        old_cycle = st.session_state.get("review_cycle", 0)
                        st.session_state["review_cycle"] = old_cycle + 1
                        for key in ['draft_content', 'checkpoint',
                                    'task_id_for_resume',
                                    f'feedback_text_input_{old_cycle}',
                                    f'review_draft_content_{old_cycle}']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                except Exception as e:
                    render_feedback_box(f"Error al enviar feedback: {e}", type_="error")
            if restart_button:
                old_cycle = st.session_state.get("review_cycle", 0)
                for key in ['draft_content', 'checkpoint', 'task_id_for_resume',
                            'generation_task_id',
                            f'feedback_text_input_{old_cycle}',
                            f'review_draft_content_{old_cycle}']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state["review_cycle"] = 0
                st.rerun()


def render_publish_ui(final_post: str, final_link_url: str, account_name: str, platform: str, account_id: str):
    with st.container(border=True):
        st.subheader("Paso 3: Publicar")
        st.caption("Revisa el contenido final y publicalo en la plataforma seleccionada.")
        edited_final_post = st.text_area(
            "",
            value=final_post or "",
            height=250,
            key="final_post_preview",
            disabled=False
        )
        st.session_state.draft_content = edited_final_post

        render_publication_controls(
            final_post=edited_final_post or "",
            final_link_url=final_link_url or "",
            selected_display_name=account_name,
            active_platform=platform,
            active_account_id=account_id or "",
            api_client_module=api_client
        )

        st.divider()
        st.caption("O guarda el post para publicarlo mas tarde:")
        if st.button("\U0001f4be Guardar para mas tarde", type="secondary", use_container_width=True):
            token = api_client._get_current_token()
            if not token:
                st.error("No hay token de autenticacion. Por favor, inicia sesion.")
            else:
                try:
                    with st.status("Guardando post..."):
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
                        st.success(f"\u2705 Post guardado para mas tarde (ID: {post_id})")
                        for key in ['draft_content', 'generation_task_id', 'checkpoint', 'task_id_for_resume']:
                            if key in st.session_state:
                                del st.session_state[key]
                        time.sleep(2)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar el post: {e}")
                    logger.error(f"Error saving post for later: {e}")


def render_page(active_context: Dict[str, Any]):
    """
    Renderiza la vista principal para la generación de contenido.

    :param active_context: Diccionario con el contexto y datos de la cuenta activa.
    :returns: None
    """
    if not active_context:
        st.error("Error interno: Se intento renderizar la pagina sin un contexto de cuenta activo.")
        return

    st.title("\u270d\ufe0f Generacion de Contenido")
    account_name = active_context.get("name", "Cuenta desconocida")
    platform = active_context.get("platform", "Plataforma desconocida")
    account_id = str(active_context.get("account_id", ""))

    if 'generation_task_id' in st.session_state and st.session_state.generation_task_id:
        render_stepper(0, ["Generando", "Revision", "Publicacion"])
        task_id = st.session_state.generation_task_id
        try:
            status_data = api_client.get_generation_status(task_id)
            status = status_data.get("status")
            if status == "SUCCESS":
                render_feedback_box("Contenido generado con exito!", type_="success")
                result = status_data.get("result", {})
                st.session_state.draft_content = result.get("final_post")
                del st.session_state.generation_task_id
                st.rerun()
            elif status == "PENDING_USER_INPUT":
                render_feedback_box("Se requiere tu revision para continuar.", type_="info")
                info = status_data.get("info", {})
                st.session_state.draft_content = info.get("draft_content")
                st.session_state.checkpoint = info.get("checkpoint")
                st.session_state.task_id_for_resume = task_id
                del st.session_state.generation_task_id
                st.rerun()
            elif status == "FAILURE":
                render_feedback_box(f"Error en la generacion: {status_data.get('error', 'Error desconocido')}", type_="error")
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
            render_stepper(1, ["Generando", "Revision", "Publicacion"])
            render_review_ui(
                draft_content=st.session_state.draft_content or "",
                checkpoint=st.session_state.checkpoint or "",
                task_id_for_resume=st.session_state.task_id_for_resume or ""
            )
        else:
            render_stepper(2, ["Generando", "Revision", "Publicacion"])
            render_publish_ui(
                final_post=st.session_state.draft_content or "",
                final_link_url=st.session_state.get("draft_link_url", "") or "",
                account_name=account_name,
                platform=platform,
                account_id=account_id or ""
            )
    else:
        render_stepper(0, ["Generando", "Revision", "Publicacion"])
        niche, tone, query, link_url, submitted = render_generation_form()
        if submitted:
            if not query or not niche:
                render_feedback_box("Por favor, completa los campos 'Nicho' y 'Descripcion'.", type_="warning")
            else:
                try:
                    with st.status("Enviando tu solicitud a la IA..."):
                        task_id = api_client.start_content_generation(
                            tone=tone, query=query, niche=niche,
                            account_name=account_name, selected_account=st.session_state.selected_account, link_url=link_url
                        )
                        st.session_state.generation_task_id = task_id
                        st.session_state.draft_link_url = link_url
                        st.rerun()
                except Exception as e:
                    render_feedback_box(f"Error al iniciar la generacion: {e}", type_="error")
