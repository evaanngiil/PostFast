import streamlit as st
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List
import pandas as pd

from src.services import api_client
from src.core.logger import logger


# Custom CSS -- AIPost brand palette.
#   Teal:     #00A99D / #007A70
#   Charcoal: #473E40
#   Muted:    #495f5e
#   BG Light: #F0F2F6

def _inject_custom_css():
    st.markdown("""
    <style>
    /* ── Bootstrap Icons (shared with sidebar) ───────────────────────── */
    @import url("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css");

    /* ── Stats banner (teal gradient, same as Dashboard metrics-banner) ── */
    .stats-banner {
        background: linear-gradient(135deg, #00A99D 0%, #007A70 100%);
        border-radius: 14px;
        padding: 1.25rem 1.75rem;
        margin-bottom: 1.75rem;
        color: white;
        display: flex;
        gap: 2rem;
        flex-wrap: wrap;
    }
    .stat-item { text-align: center; flex: 1; min-width: 100px; }
    .stat-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: white;
        line-height: 1.2;
    }
    .stat-label {
        font-size: .8rem;
        color: rgba(255,255,255,.85);
        margin-top: .15rem;
    }

    /* ── Post cards ──────────────────────────────────────────────────── */
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) {
        transition: transform .2s, box-shadow .2s;
    }
    [data-testid="stExpander"] {
        border-color: rgba(0, 169, 157, .15) !important;
        border-radius: 10px !important;
    }

    /* ── Status badges ───────────────────────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: .73rem;
        font-weight: 600;
        letter-spacing: .4px;
        text-transform: uppercase;
    }
    .badge-saved     { background: #fff3e0; color: #e65100; }
    .badge-scheduled { background: #e0f7f5; color: #007A70; }
    .badge-published { background: #d4edda; color: #155724; }
    .badge-draft     { background: #f3e5f5; color: #6a1b9a; }
    .badge-default   { background: #eceff1; color: #546e7a; }

    /* ── Platform chips ──────────────────────────────────────────────── */
    .platform-chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 10px;
        border-radius: 8px;
        font-size: .76rem;
        font-weight: 500;
        background: rgba(0, 169, 157, .08);
        color: #495f5e;
    }

    /* ── Card header row ─────────────────────────────────────────────── */
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
    }
    .card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1a1a2e;
        margin: 0;
    }
    .card-badges { display: flex; gap: 8px; align-items: center; }

    /* ── Timestamps ──────────────────────────────────────────────────── */
    .ts-row { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 6px; }
    .ts-info {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: #495f5e;
        font-size: .78rem;
    }

    /* ── Content preview ─────────────────────────────────────────────── */
    .content-preview {
        color: #495f5e;
        font-size: .9rem;
        line-height: 1.65;
        margin-top: .75rem;
        padding: .75rem 1rem;
        background: #f8f9fa;
        border-radius: 10px;
        border-left: 3px solid #00A99D;
    }

    /* ── Section headers ─────────────────────────────────────────────── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 1.25rem 0 .85rem;
        padding-bottom: .5rem;
        border-bottom: 2px solid rgba(0, 169, 157, .2);
    }
    .section-header h3 {
        margin: 0;
        font-weight: 700;
        font-size: 1.15rem;
        color: #1a1a2e;
    }

    /* ── Filter & form containers use st.container(border=True) ─────── */
    /* No custom wrapper divs needed -- Streamlit handles the border.  */
    /* We just style the native bordered container for a cleaner look. */

    /* ── Empty state ─────────────────────────────────────────────────── */
    .pm-empty {
        text-align: center;
        padding: 3rem 1rem;
        color: #495f5e;
    }
    .pm-empty .icon { font-size: 3rem; margin-bottom: .5rem; }
    .pm-empty p { margin: .25rem 0; }
    .pm-empty strong { color: #473E40; }

    /* ── Card-level buttons ──────────────────────────────────────────── */
    div[data-testid="stVerticalBlock"] .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        font-size: .85rem;
        transition: transform .15s, box-shadow .15s;
    }
    div[data-testid="stVerticalBlock"] .stButton > button:hover {
        transform: scale(1.03);
        box-shadow: 0 2px 8px rgba(0,169,157,.15);
    }

    /* ── Bordered containers (filter bar, forms, post cards) ────────── */
    [data-testid="stContainer"] {
        border-radius: 14px !important;
    }
    </style>
    """, unsafe_allow_html=True)


# Funciones auxiliares de utilidad.

_STATUS_META = {
    "saved_for_later": {"label": "Guardado",  "badge": "badge-saved",     "icon": "bi-bookmark-fill",  "emoji": "🔖"},
    "scheduled":       {"label": "Programado", "badge": "badge-scheduled", "icon": "bi-calendar-event", "emoji": "📅"},
    "published":       {"label": "Publicado",  "badge": "badge-published", "icon": "bi-check-circle-fill", "emoji": "✅"},
    "draft":           {"label": "Borrador",   "badge": "badge-draft",     "icon": "bi-pencil-square",  "emoji": "📝"},
}

_PLATFORM_ICONS = {
    "linkedin":  "bi-linkedin",
    "twitter":   "bi-twitter-x",
    "x":         "bi-twitter-x",
    "facebook":  "bi-facebook",
    "instagram": "bi-instagram",
}


def _status_badge_html(status: str) -> str:
    meta = _STATUS_META.get(status, {"label": status.replace("_", " ").title(), "badge": "badge-default", "icon": "bi-pin-angle-fill"})
    return f'<span class="badge {meta["badge"]}"><i class="bi {meta["icon"]}" style="font-size:.7rem;"></i> {meta["label"]}</span>'


def _platform_chip_html(platform: str) -> str:
    icon = _PLATFORM_ICONS.get(platform.lower(), "bi-globe")
    return f'<span class="platform-chip"><i class="bi {icon}"></i> {platform.title()}</span>'


def _format_datetime(iso_str: str) -> str:
    """
    Convierte un string ISO a un formato de fecha legible.

    :param iso_str: String de la fecha en formato ISO.
    :returns: String con la fecha formateada.
    """
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso_str[:19] if iso_str else "N/A"


# Clientes y handlers para integraciones API.

def get_posts_from_api(status: str = None, account_id: str = None) -> List[Dict[str, Any]]:
    """
    Obtiene posts del backend mediante fetch, con soporte para filtros de estado.

    :param status: Filtro opcional de estado del post (ej. publicado, borrador).
    :param account_id: ID del perfil destino.
    :returns: Una lista de diccionarios con el payload de los posts.
    """
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticacion. Por favor, inicia sesion.")
        return []
    try:
        params = {}
        if status:
            params["status"] = status
        if account_id:
            params["account_id"] = account_id
        response = requests.get(
            f"{api_client.FASTAPI_URL}/content/posts",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching posts: {e}")
        st.error(f"Error al obtener posts: {e}")
        return []


def delete_post_from_api(post_id: str) -> bool:
    """
    Llamada API para eliminar permanentemente un post.

    :param post_id: Identificador único del post.
    :returns: True si el delete fue exitoso, False si falló.
    """
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticacion. Por favor, inicia sesion.")
        return False
    try:
        response = requests.delete(
            f"{api_client.FASTAPI_URL}/content/posts/{post_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        st.error(f"Error al eliminar post: {e}")
        return False


def update_post_from_api(post_id: str, updates: Dict[str, Any]) -> bool:
    """
    Actualiza los datos parciales o totales de un post vía PUT.

    :param post_id: ID base de datos del post.
    :param updates: Diccionario con el payload a modificar.
    :returns: True en caso de éxito, de lo contrario False.
    """
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticacion. Por favor, inicia sesion.")
        return False
    try:
        response = requests.put(
            f"{api_client.FASTAPI_URL}/content/posts/{post_id}",
            json=updates,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {e}")
        st.error(f"Error al actualizar post: {e}")
        return False


def publish_post_from_api(post_id: str, platform: str, account_id: str) -> bool:
    """
    Llamada para desencadenar el envío (publish) o programación de un post guardado.

    :param post_id: Identificador del post en BD.
    :param platform: Red social destino.
    :param account_id: ID de la cuenta vinculada.
    :returns: True si la operación de dispatch fue exitosa, False en caso de error.
    """
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticacion. Por favor, inicia sesion.")
        return False
    try:
        response = requests.get(
            f"{api_client.FASTAPI_URL}/content/posts/{post_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        post_data = response.json()

        publish_response = requests.post(
            f"{api_client.FASTAPI_URL}/content/schedule_post",
            json={
                "platform": platform,
                "account_id": account_id,
                "content": post_data["content"],
                "link_url": post_data.get("link_url"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        publish_response.raise_for_status()

        update_post_from_api(post_id, {
            "status": "published",
            "published_time": datetime.now(timezone.utc).isoformat(),
        })
        return True
    except Exception as e:
        logger.error(f"Error publishing post {post_id}: {e}")
        st.error(f"Error al publicar post: {e}")
        return False


# Renderizado visual y componentes UI.

def render_post_card(post: Dict[str, Any], context: Dict[str, Any]):
    """
    Componente visual que muestra los detalles, estatus y métricas de un post individual.

    :param post: Diccionario de datos del post.
    :param context: Contexto actual del entorno.
    :returns: None
    """

    status = post.get("status", "")
    platform = post.get("platform", "")
    title = post.get("title", "Sin titulo")
    content = post.get("content", "")
    created = post.get("created_at", "")
    scheduled = post.get("scheduled_time")
    published = post.get("published_time")

    with st.container(border=True):
        # ── Header: titulo + badges ─────────────────────────────────
        st.markdown(f"""
        <div class="card-header">
            <p class="card-title">{title}</p>
            <div class="card-badges">
                {_platform_chip_html(platform)}
                {_status_badge_html(status)}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Timestamps ──────────────────────────────────────────────
        ts_parts = [f'<span class="ts-info"><i class="bi bi-clock"></i> Creado: {_format_datetime(created)}</span>']
        if scheduled:
            ts_parts.append(f'<span class="ts-info"><i class="bi bi-calendar-event"></i> Programado: {_format_datetime(scheduled)}</span>')
        if published:
            ts_parts.append(f'<span class="ts-info"><i class="bi bi-check-circle"></i> Publicado: {_format_datetime(published)}</span>')
        st.markdown(f'<div class="ts-row">{"".join(ts_parts)}</div>', unsafe_allow_html=True)

        # ── Content preview ─────────────────────────────────────────
        if content:
            preview = content[:220].replace("\n", "<br>")
            is_long = len(content) > 220
            st.markdown(
                f'<div class="content-preview">{preview}{"..." if is_long else ""}</div>',
                unsafe_allow_html=True,
            )
            if is_long:
                with st.expander("Ver contenido completo"):
                    st.write(content)

        # ── Action buttons ──────────────────────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        btn_cols = st.columns([1, 1, 1, 2])

        if status == "saved_for_later":
            with btn_cols[0]:
                if st.button("Publicar", key=f"pub_{post['id']}", use_container_width=True, icon=":material/send:"):
                    if publish_post_from_api(post["id"], platform, post["account_id"]):
                        st.success("Post publicado!")
                        st.rerun()
            with btn_cols[1]:
                if st.button("Editar", key=f"edit_{post['id']}", use_container_width=True, icon=":material/edit:"):
                    st.session_state["editing_post"] = post
                    st.rerun()
            with btn_cols[2]:
                if st.button("Eliminar", key=f"del_{post['id']}", use_container_width=True, type="secondary", icon=":material/delete:"):
                    if delete_post_from_api(post["id"]):
                        st.success("Post eliminado!")
                        st.rerun()

        elif status == "scheduled":
            with btn_cols[0]:
                if st.button("Reprogramar", key=f"resched_{post['id']}", use_container_width=True, icon=":material/schedule:"):
                    st.session_state["rescheduling_post"] = post
                    st.rerun()
            with btn_cols[1]:
                if st.button("Eliminar", key=f"del_{post['id']}", use_container_width=True, type="secondary", icon=":material/delete:"):
                    if delete_post_from_api(post["id"]):
                        st.success("Post eliminado!")
                        st.rerun()

        else:
            with btn_cols[0]:
                if st.button("Eliminar", key=f"del_{post['id']}", use_container_width=True, type="secondary", icon=":material/delete:"):
                    if delete_post_from_api(post["id"]):
                        st.success("Post eliminado!")
                        st.rerun()


def render_edit_form(post: Dict[str, Any]):
    """
    Componente que renderiza el formulario in-line para mutar el contenido del post.

    :param post: Diccionario con los datos previos del post.
    :returns: None
    """
    with st.container(border=True):
        st.markdown(
            '<div class="section-header"><h3><i class="bi bi-pencil-square" style="color:#00A99D;"></i> Editar Post</h3></div>',
            unsafe_allow_html=True,
        )

        with st.form(f"edit_form_{post['id']}"):
            title = st.text_input("Titulo", value=post.get("title", ""), placeholder="Escribe un titulo...")
            content = st.text_area("Contenido", value=post.get("content", ""), height=220, placeholder="Escribe el contenido del post...")

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            col1, col2, _ = st.columns([1, 1, 3])
            with col1:
                save = st.form_submit_button("Guardar cambios", type="primary", icon=":material/save:")
            with col2:
                cancel = st.form_submit_button("Cancelar")

            if save:
                updates = {"title": title, "content": content}
                if update_post_from_api(post["id"], updates):
                    st.success("Post actualizado correctamente.")
                    del st.session_state["editing_post"]
                    st.rerun()
            if cancel:
                del st.session_state["editing_post"]
                st.rerun()


def render_reschedule_form(post: Dict[str, Any]):
    """
    Componente UI para actualizar el cron de publicación de un post ya calendarizado.

    :param post: Diccionario de datos del post original.
    :returns: None
    """
    with st.container(border=True):
        st.markdown(
            '<div class="section-header"><h3><i class="bi bi-calendar2-week" style="color:#00A99D;"></i> Reprogramar Post</h3></div>',
            unsafe_allow_html=True,
        )

        with st.form(f"reschedule_form_{post['id']}"):
            default_dt = datetime.now(timezone.utc)
            if post.get("scheduled_time"):
                try:
                    default_dt = datetime.fromisoformat(post["scheduled_time"].replace("Z", "+00:00"))
                except Exception:
                    pass

            new_time = st.datetime_input(
                "Nueva fecha y hora",
                value=default_dt,
                min_value=datetime.now(timezone.utc),
            )

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            col1, col2, _ = st.columns([1, 1, 3])
            with col1:
                save = st.form_submit_button("Reprogramar", type="primary", icon=":material/schedule:")
            with col2:
                cancel = st.form_submit_button("Cancelar")

            if save:
                updates = {"scheduled_time": new_time.isoformat()}
                if update_post_from_api(post["id"], updates):
                    st.success("Post reprogramado correctamente.")
                    del st.session_state["rescheduling_post"]
                    st.rerun()
            if cancel:
                del st.session_state["rescheduling_post"]
                st.rerun()


# Entrypoint de la vista.

def render_page(context: Dict[str, Any]):
    """
    Flujo principal de renderizado del gestor de publicaciones.

    :param context: Configuración y estado global inyectado.
    :returns: None
    """
    _inject_custom_css()

    # No renderizamos titulo — lo gestiona Posts_Management.py (controlador)

    if not context.get("data"):
        st.markdown("""
        <div class="pm-empty">
            <div class="icon"><i class="bi bi-folder2-open" style="font-size:3rem; color:#00A99D;"></i></div>
            <p><strong>Sin cuenta seleccionada</strong></p>
            <p>Selecciona una cuenta en la barra lateral para ver tus posts.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Filter bar ──────────────────────────────────────────────────
    with st.container(border=True):
        fcol1, fcol2, fcol3 = st.columns([2.5, 1, 1])
        with fcol1:
            status_filter = st.selectbox(
                "Filtrar por estado",
                ["Todos", "Guardados para mas tarde", "Programados", "Publicados"],
                index=0,
                label_visibility="collapsed",
            )
        with fcol3:
            if st.button("Actualizar", use_container_width=True, icon=":material/refresh:"):
                st.rerun()

    # ── Edit / Reschedule forms (overlay) ───────────────────────────
    if "editing_post" in st.session_state:
        render_edit_form(st.session_state["editing_post"])
        return

    if "rescheduling_post" in st.session_state:
        render_reschedule_form(st.session_state["rescheduling_post"])
        return

    # ── Fetch posts ─────────────────────────────────────────────────
    status_mapping = {
        "Todos": None,
        "Guardados para mas tarde": "saved_for_later",
        "Programados": "scheduled",
        "Publicados": "published",
    }
    status_param = status_mapping.get(status_filter)
    active_account_id = context.get("account_id") or None
    logger.warning(f"Active account ID: {active_account_id}")
    posts = get_posts_from_api(status_param, account_id=active_account_id)

    if not posts:
        label = status_filter.lower() if status_filter != "Todos" else ""
        st.markdown(f"""
        <div class="pm-empty">
            <div class="icon"><i class="bi bi-inbox" style="font-size:3rem; color:#00A99D;"></i></div>
            <p><strong>No hay posts {label}</strong></p>
            <p>Crea contenido nuevo para empezar.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Statistics banner (teal gradient, matching Dashboard) ───────
    status_counts: Dict[str, int] = {}
    for p in posts:
        s = p["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    stat_items_html = ""
    for status_key, count in status_counts.items():
        meta = _STATUS_META.get(status_key, {"label": status_key.replace("_", " ").title(), "icon": "bi-pin-angle-fill"})
        stat_items_html += f"""
        <div class="stat-item">
            <div class="stat-value">{count}</div>
            <div class="stat-label"><i class="bi {meta['icon']}"></i> {meta['label']}</div>
        </div>"""

    # Agregar total
    stat_items_html += f"""
    <div class="stat-item">
        <div class="stat-value">{len(posts)}</div>
        <div class="stat-label"><i class="bi bi-collection"></i> Total</div>
    </div>"""

    st.markdown(f'<div class="stats-banner">{stat_items_html}</div>', unsafe_allow_html=True)

    # ── Post list ───────────────────────────────────────────────────
    st.markdown(
        f'<div class="section-header">'
        f'<h3><i class="bi bi-stack" style="color:#00A99D;"></i> Posts'
        f'&nbsp;<span style="font-weight:400;color:#495f5e;font-size:.9rem;">({len(posts)} encontrados)</span></h3>'
        f'</div>',
        unsafe_allow_html=True,
    )

    posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    for post in posts:
        render_post_card(post, context)
