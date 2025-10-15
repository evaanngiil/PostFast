import streamlit as st
from src.supabase_auth import revalidate_aipost_session, is_aipost_logged_in
from src.linkedin_auth import verify_session_on_load, load_user_accounts, ensure_session_initialized, process_auth_params
from src.components.sidebar import render_sidebar
from src.utils.context import get_selected_account_context
from src.pages import content_generation
from src.components.ui_helpers import set_page_config

# --- CONFIGURACIÓN DE PÁGINA ---
set_page_config("AIPost - Generación de Contenido")

# Inicializa sesión (mantiene al usuario logueado al navegar)
ensure_session_initialized()

# --- GUARD DE AUTENTICACIÓN Y VALIDACIÓN DE SESIÓN ---
revalidate_aipost_session()

if not is_aipost_logged_in():
    st.warning("Debes iniciar sesión para acceder a esta página.")
    st.switch_page("app.py")

# --- LÓGICA DE INICIALIZACIÓN DE LINKEDIN ---
try:
    verify_session_on_load()
    if st.session_state.get("li_connected"):
        load_user_accounts("LinkedIn")
except Exception as e:
    st.error(f"Error al inicializar la sesión de LinkedIn: {e}")

# --- RENDERIZADO DE LA PÁGINA ---
# Renderizar la barra lateral y obtener el contexto de la cuenta seleccionada
selected_account_data = render_sidebar()

# Comprobar si el usuario ha conectado LinkedIn y ha seleccionado una cuenta.
if not st.session_state.get("li_connected"):
    st.info("💡 Para generar contenido, primero debes conectar tu cuenta de LinkedIn.")
    st.markdown("#### Pasos a seguir:")
    st.markdown("1. Abre la barra lateral (si está cerrada).")
    st.markdown("2. Haz clic en el botón **Connect LinkedIn**.")
    st.markdown("3. Autoriza la conexión en la ventana de LinkedIn.")
    st.stop() # Detiene la ejecución del script para no continuar

if not selected_account_data:
    st.info("👈 Por favor, selecciona un perfil o una página de organización en la barra lateral para comenzar.")
    st.stop() # Detiene la ejecución del script

active_context = get_selected_account_context(selected_account_data)
# Llamar a la función de renderizado principal del módulo de generación
content_generation.render_page(active_context)