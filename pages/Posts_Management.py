import streamlit as st
from src.linkedin_auth import ensure_auth
from src.components.sidebar import render_sidebar
from src.utils.context import get_selected_account_context
from src.pages import posts_management
from src.core.logger import logger
from src.components.ui_helpers import set_page_config

set_page_config("AIPost - Publicaciones")

ensure_auth(protect_route=True)

user = st.session_state.get('user')

st.markdown("""
<style>
    .pm-page-header { font-size: 2.2rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0; }
    .pm-page-subtitle { font-size: 1.05rem; color: #495f5e; margin-bottom: 1.5rem; }
</style>
<div class="pm-page-header">Gestion de Publicaciones</div>
<div class="pm-page-subtitle">Administra, edita y publica tus posts en redes sociales desde un solo lugar.</div>
""", unsafe_allow_html=True)

selected_account_data = render_sidebar(user)

# Comprobar si el usuario ha conectado LinkedIn y ha seleccionado una cuenta.
if not st.session_state.get("li_connected"):
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-left: 4px solid #00A99D;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        color: #495f5e;
    ">
        <p style="font-weight:600; color:#473E40; margin:0 0 .75rem 0;">
            Para gestionar tus posts, primero debes conectar tu cuenta de LinkedIn.
        </p>
        <ol style="margin:0; padding-left:1.25rem; line-height:1.8;">
            <li>Abre la barra lateral (si esta cerrada).</li>
            <li>Haz clic en el boton <strong>Connect LinkedIn</strong>.</li>
            <li>Autoriza la conexion en la ventana de LinkedIn.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not selected_account_data:
    st.info("Por favor, selecciona un perfil o una pagina de organizacion en la barra lateral para ver tus posts.")
    st.stop()

# Si pasamos las comprobaciones, podemos obtener el contexto y renderizar la pagina
active_context = get_selected_account_context(selected_account_data)
logger.warning(f"Active context: {active_context}")
posts_management.render_page(active_context)
