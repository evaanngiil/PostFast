import streamlit as st
from src.linkedin_auth import ensure_auth
from src.components.sidebar import render_sidebar
from src.components.ui_helpers import set_page_config

# --- INICIALIZACIÓN Y AUTENTICACIÓN ---
set_page_config("AIPost - Dashboard")
ensure_auth(protect_route=True)


# --- RENDERIZADO DEL SIDEBAR ---
selected_account = render_sidebar()

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

content_gen_url = "/Generate_Content"
posts_mgmt_url = "/Post_Managment"

# --- DATOS DEL USUARIO ---
# Obtenemos el usuario de st.session_state, que ya fue poblado por ensure_auth()
user = st.session_state.get('user')
welcome_name = ""
if user:
    # Intenta obtener el nombre desde user.user_metadata, que es más estándar en Supabase
    welcome_name = user.user_metadata.get('name', user.email)

# --- ENCABEZADO ---
st.markdown(f"<div class='dashboard-header'>👋 ¡Hola, {welcome_name}!</div>", unsafe_allow_html=True)
st.markdown("<div class='dashboard-subtitle'>Accede rápidamente a tus herramientas para crear, gestionar y analizar contenido.</div>", unsafe_allow_html=True)

# --- ACCIONES PRINCIPALES ---
st.subheader("🚀 Acciones principales")

col1, col2 = st.columns(2, gap="large")
with col1:
    st.markdown(f"""
    <a href="{content_gen_url}" target="_self" class="clickable-card">
        <div class="card">
            <h3>✍️ Generación de Contenido</h3>
            <p>Crea publicaciones optimizadas y originales utilizando inteligencia artificial. Define tu estilo y deja que la magia suceda.</p>
        </div>
    </a>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <a href="{posts_mgmt_url}" target="_self" class="clickable-card">
        <div class="card">
            <h3>📝 Gestión de Posts</h3>
            <p>Revisa, organiza y programa tus publicaciones. Visualiza tu calendario editorial y mantén el control de tu contenido.</p>
        </div>
    </a>
    """, unsafe_allow_html=True)


# --- CONEXIONES ---
st.markdown('<div style="margin:2rem 0 1rem 0;"><h3 style="margin-bottom:0;">🔗 Estado de Conexión</h3></div>', unsafe_allow_html=True)

# La lógica ahora es mucho más simple: solo comprobamos el estado en session_state
if st.session_state.get("li_connected"):
    user_info = st.session_state.get("li_user_info", {})
    li_name = user_info.get("name", "Usuario de LinkedIn")

    st.markdown(f"""
    <div class="connection-box">
        ✅ Conectado a LinkedIn como <strong>{li_name}</strong>.
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="connection-box" style="border-left-color: #E8B200;">
        ⚠️ No has conectado tu cuenta de LinkedIn. Ve a la barra lateral para autorizar el acceso.
    </div>
    """, unsafe_allow_html=True)