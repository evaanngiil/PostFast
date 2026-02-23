import streamlit as st
import base64

# --- Core Imports ---
try:
    from src.supabase_auth import login, signup
    from src.linkedin_auth import ensure_auth
    from src.components.ui_helpers import set_page_config
    from src.core.logger import logger
except ImportError as e:
    st.error(f"Error crítico al importar módulos: {e}")
    st.stop()

# --- INICIALIZACIÓN Y LÓGICA DE AUTENTICACIÓN ---
set_page_config("AIPost - Login")

# Le pasamos protect_route=False porque esta es la página de login.
ensure_auth(protect_route=False)

# --- LÓGICA DE REDIRECCIÓN CENTRALIZADA ---
# Si después de `ensure_auth`, el estado indica que el usuario está logueado,
# lo redirigimos al dashboard. Esta es la única fuente de verdad.
if st.session_state.get('aipost_logged_in'):
    st.switch_page("pages/Dashboard.py")

# El resto del script solo se ejecutará si el usuario NO está logueado.

# --- FUNCIÓN HELPER ---
def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        st.warning(f"No se encontró la imagen de fondo en: {file}")
        return ""

# --- CONFIGURACIÓN Y ESTILOS ---
img = get_img_as_base64("./src/assets/login_bg_full2.jpg")

page_bg_img = f"""
    <style>
        /* Ocultar la decoración del menú de Streamlit */
        #MainMenu, header, footer {{visibility: hidden;}}
        .block-container {{ padding: 0 !important; margin: 0 !important; }}
        body {{
            min-height: 100vh !important;
            min-width: 100vw !important;
            background-image: url("data:image/png;base64,{img}");
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
        }}
        .stApp {{
            min-height: 100vh !important;
            min-width: 100vw !important;
            background: transparent !important;
        }}
        [data-testid="stHorizontalBlock"] {{
            height: 100vh;
            background: transparent !important;
            align-items: center;
        }}
        [data-testid="stHorizontalBlock"] > div:nth-child(1) {{
            padding: 0 !important;
            height: 100vh;
            background: transparent !important;
        }}
        [data-testid="stImage"] img {{ display: none !important; }}
        [data-testid="stHorizontalBlock"] > div:nth-child(2) {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            backdrop-filter: blur(2px);
        }}
        [data-testid="stHorizontalBlock"] > div:nth-child(2) > div {{
            width: 80%;
            max-width: 450px;
            padding: 2.5rem;
            background-color: white;
            border-radius: 15px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.1);
            animation: fadeIn 0.8s ease-in-out;
        }}
        @media (max-width: 768px) {{
            [data-testid="stHorizontalBlock"] > div:nth-child(1) {{ display: none; }}
            [data-testid="stHorizontalBlock"] > div:nth-child(2) {{
                background-color: rgba(255,255,255,0.93);
                backdrop-filter: blur(0px);
            }}
            [data-testid="stHorizontalBlock"] > div:nth-child(2) > div {{
                width: 100%;
                box-shadow: none;
            }}
        }}
        @keyframes fadeIn {{
            from {{opacity: 0; transform: translateY(20px);}}
            to {{opacity: 1; transform: translateY(0);}}
        }}
        button[data-baseweb="tab"] {{ font-size: 18px !important; }}
        .stButton > button {{ transition: transform 0.2s ease-in-out; }}
        .stButton > button:hover {{ transform: scale(1.02); }}
    </style>
"""

st.markdown(page_bg_img, unsafe_allow_html=True)


# --- LAYOUT DE LA PÁGINA DE LOGIN---
col_img, col_form = st.columns([0.9, 0.9], gap="small")

with col_form:
    st.title("Bienvenido a AIPost")
    st.markdown("Accede o crea una cuenta para empezar a generar contenido con IA.")

    login_tab, signup_tab = st.tabs(["**Iniciar Sesión**", "**Crear Cuenta**"])

    # --- FORMULARIO DE LOGIN ---
    with login_tab:
        with st.form("login_form"):
            st.text_input("Email", placeholder="tu@email.com", key="login_email")
            st.text_input("Contraseña", type="password", placeholder="••••••••", key="login_password")
            if st.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary"):
                if login(st.session_state.login_email, st.session_state.login_password):
                    # Si el login tiene éxito, simplemente hacemos un rerun.
                    # La lógica de redirección de arriba se encargará del resto.
                    st.switch_page("pages/Dashboard.py")
                else:
                    # La función login ya muestra un st.error o st.warning,
                    # por lo que no es necesario mostrar otro mensaje aquí.
                    pass


    # --- FORMULARIO DE REGISTRO ---
with signup_tab:
        with st.form("signup_form"):
            
            st.text_input("Nombre", key="signup_first_name", placeholder="Ana")
            st.text_input("Apellidos", key="signup_last_name", placeholder="García")

            st.text_input("Email", key="signup_email", placeholder="tu@email.com")
            st.text_input("Crea una contraseña", type="password", key="signup_password")
            st.text_input("Confirma tu contraseña", type="password", key="confirm_password")
            st.checkbox("Acepto los Términos y la Política de Privacidad.", key="terms")
            
            if st.form_submit_button("Crear Cuenta", use_container_width=True, type="primary"):
                
                if not st.session_state.signup_first_name or not st.session_state.signup_last_name:
                    st.error("Debes introducir tu nombre y apellidos.")
                elif not st.session_state.terms:
                    st.error("Debes aceptar los términos y condiciones.")
                elif st.session_state.signup_password != st.session_state.confirm_password:
                    st.error("Las contraseñas no coinciden.")
                else:
                    signup(
                        st.session_state.signup_email, 
                        st.session_state.signup_password, 
                        st.session_state.signup_first_name,
                        st.session_state.signup_last_name
                    )