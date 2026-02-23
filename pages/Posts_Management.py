import streamlit as st
from src.linkedin_auth import  ensure_auth
from src.components.sidebar import render_sidebar
from src.supabase_auth import get_user_profile, get_current_user
from src.utils.context import get_selected_account_context
from src.pages import posts_management
from src.components.ui_helpers import set_page_config

# --- CONFIGURACIÓN DE PÁGINA ---
set_page_config("AIPost - Publicaciones")
ensure_auth(protect_route=True)

# --- RENDERIZADO DE LA PÁGINA ---
user = get_current_user()
selected_account_data = render_sidebar(user)

# Comprobar si el usuario ha conectado LinkedIn y ha seleccionado una cuenta.
if not st.session_state.get("li_connected"):
    st.info("💡 Para gestionar tus posts, primero debes conectar tu cuenta de LinkedIn.")
    st.markdown("#### Pasos a seguir:")
    st.markdown("1. Abre la barra lateral (si está cerrada).")
    st.markdown("2. Haz clic en el botón **Connect LinkedIn**.")
    st.markdown("3. Autoriza la conexión en la ventana de LinkedIn.")
    st.stop()

if not selected_account_data:
    st.info("👈 Por favor, selecciona un perfil o una página de organización en la barra lateral para ver tus posts.")
    st.stop()

# Si pasamos las comprobaciones, podemos obtener el contexto y renderizar la página
active_context = get_selected_account_context(selected_account_data)
posts_management.render_page(active_context)