import streamlit as st
from src.supabase_auth import logout, revalidate_aipost_session, is_aipost_logged_in
from src.linkedin_auth import verify_session_on_load, load_user_accounts, ensure_session_initialized
from src.components.sidebar import render_sidebar
from src.components.ui_helpers import set_page_config

# --- CONFIGURACIÓN DE PÁGINA ---
set_page_config("AIPost - Dashboard")

# Inicializa sesión (mantiene al usuario logueado al navegar)
ensure_session_initialized()

# --- AUTENTICACIÓN ---
# Evitar redirección prematura al login cuando estamos en el flujo de verificación
client_verified_flag = st.session_state.get('client_verified') or bool(st.query_params.get('client_verified'))

if not is_aipost_logged_in() and not client_verified_flag:
    st.warning("Debes iniciar sesión para acceder a esta página.")
    st.switch_page("app.py")

# --- SESIÓN LINKEDIN ---
try:
    verify_session_on_load()
    if st.session_state.get("li_connected"):
        load_user_accounts("LinkedIn")
except Exception as e:
    st.error(f"Error al inicializar la sesión de LinkedIn: {e}")

# --- RENDER SIDEBAR ---
render_sidebar()

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
<style>
    .dashboard-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #473E40;
        margin-bottom: 0.25rem;
    }

    .dashboard-subtitle {
        font-size: 1.1rem;
        color: #495f5e;
        margin-bottom: 2rem;
    }

    .clickable-card {
        display: block;
        text-decoration: none !important;
        height: 100%;
    }

    .card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E0E0E0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        transition: 0.2s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 230px;
    }

    .card:hover {
        border-color: #00A99D;
        box-shadow: 0 4px 10px rgba(0, 169, 157, 0.1);
    }

    .card h3 {
        color: #473E40;
        margin-top: 0;
        margin-bottom: 0.5rem;
        font-size: 1.3rem;
    }

    .card p {
        color: #495f5e;
        margin-bottom: 0;
        font-size: 1rem;
        flex-grow: 1;
    }

    .card .cta {
        margin-top: 1.25rem;
        font-weight: 600;
        color: #00A99D;
    }

    .card .cta:hover {
        text-decoration: underline;
    }

    .connection-box {
        background-color: #F9FAFB;
        border-left: 5px solid #00A99D;
        padding: 1rem;
        border-radius: 8px;
        color: #495f5e;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- DATOS DEL USUARIO ---
user = st.session_state.get('user')
welcome_name = getattr(user, 'name', user.email) if user else "Usuario"

# --- ENCABEZADO ---
st.markdown(f"<div class='dashboard-header'>👋 ¡Hola, {welcome_name}!</div>", unsafe_allow_html=True)
st.markdown("<div class='dashboard-subtitle'>Accede rápidamente a tus herramientas para crear, gestionar y analizar contenido.</div>", unsafe_allow_html=True)

# --- ACCIONES PRINCIPALES ---
st.subheader("🚀 Acciones principales")

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div class="card">
        <h3>✍️ Generación de Contenido</h3>
        <p>Crea publicaciones optimizadas y originales utilizando inteligencia artificial. Define tu estilo y deja que la magia suceda.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Ir al Generador →", key="goto_content_generation", use_container_width=True):
        try:
            st.switch_page("Content_Generation")
        except Exception:
            st.query_params = {"page": ["Content_Generation"]}
            st.rerun()

with col2:
    st.markdown("""
    <div class="card">
        <h3>📝 Gestión de Posts</h3>
        <p>Revisa, organiza y programa tus publicaciones. Visualiza tu calendario editorial y mantén el control de tu contenido.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Gestionar mis Posts →", key="goto_posts_management", use_container_width=True):
        try:
            st.switch_page("Posts_Management")
        except Exception:
            st.query_params = {"page": ["Posts_Management"]}
            st.rerun()

# --- CONEXIONES ---
st.markdown('<div style="margin:10px 0;"><h3 style="margin-bottom:0;">🔗 Estado de Conexión</h3></div>', unsafe_allow_html=True)

if st.session_state.get("li_connected"):
    user_info = st.session_state.get("li_user_info", {})
    li_name = user_info.get("name", "Usuario de LinkedIn")

    st.markdown(f"""
    <div class="connection-box" style="margin-top: 10px;">
        ✅ Conectado a LinkedIn como <strong>{li_name}</strong>.
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="connection-box" style="border-left-color: #E8B200; margin-top: 10px;">
        ⚠️ No has conectado tu cuenta de LinkedIn. Ve a la barra lateral para autorizar el acceso.
    </div>
    """, unsafe_allow_html=True)
