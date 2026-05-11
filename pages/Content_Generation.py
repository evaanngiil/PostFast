import streamlit as st
from src.linkedin_auth import ensure_auth
from src.components.sidebar import render_sidebar
from src.utils.context import get_selected_account_context
from src.pages import content_generation
from src.components.ui_helpers import set_page_config

# --- CONFIGURACION DE PAGINA ---
set_page_config("AIPost - Generacion de Contenido")

ensure_auth(protect_route=True)

user = st.session_state.get('user')

st.markdown("## Generacion de Contenido")

selected_account_data = render_sidebar(user)

# Comprobar si el usuario ha conectado LinkedIn y ha seleccionado una cuenta.
if not st.session_state.get("li_connected"):
    st.info("Para generar contenido, primero debes conectar tu cuenta de LinkedIn.")
    st.markdown("#### Pasos a seguir:")
    st.markdown("1. Abre la barra lateral (si esta cerrada).")
    st.markdown("2. Haz clic en el boton **Connect LinkedIn**.")
    st.markdown("3. Autoriza la conexion en la ventana de LinkedIn.")
    st.stop()

if not selected_account_data:
    st.info("Por favor, selecciona un perfil o una pagina de organizacion en la barra lateral para comenzar.")
    st.stop()

active_context = get_selected_account_context(selected_account_data)
# Llamar a la funcion de renderizado principal del modulo de generacion
content_generation.render_page(active_context)
