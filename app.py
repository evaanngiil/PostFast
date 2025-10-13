import streamlit as st
import base64

# --- Core Imports ---
try:
    from src.supabase_auth import login, signup, revalidate_aipost_session, initialize_aipost_session, is_aipost_logged_in
    from src.linkedin_auth import process_auth_params, initialize_session_state
    from src.components.ui_helpers import set_page_config
    from src.core.constants import FASTAPI_URL
except ImportError as e:
    st.error(f"Error crítico al importar módulos: {e}")
    st.stop()

def get_img_as_base64(file):
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        st.warning(f"No se encontró la imagen de fondo en: {file}")
        return ""

# --- CONFIGURACIÓN Y ESTILOS ---
set_page_config("AIPost - Login")
img = get_img_as_base64("./src/assets/login_bg_full2.jpg")

page_bg_img = f"""
    <style>
        /* Ocultar la decoración del menú de Streamlit */
        #MainMenu, header, footer {{visibility: hidden;}}

        /* Eliminar el padding del contenedor principal de la app */
        .block-container {{
            padding: 0 !important;
            margin: 0 !important;
        }}

        /* Hacer que el body ocupe toda la ventana y colocar el background image */
        body {{
            min-height: 100vh !important;
            min-width: 100vw !important;
            background-image: url("data:image/png;base64,{img}");
            background-size: cover; /* Cambiado a 'cover' para llenar el espacio */
            background-position: center center;
            background-repeat: no-repeat;
        }}

        /* Para Streamlit 1.x, también debemos cubrir el app root */
        .stApp {{
            min-height: 100vh !important;
            min-width: 100vw !important;
            background: transparent !important; /* Transparente para heredar el fondo del body */
        }}

        /* Asegurar que el layout de columnas ocupe toda la altura y que sea transparente */
        [data-testid="stHorizontalBlock"] {{
            height: 100vh;
            background: transparent !important;
            align-items: center;
        }}

        /* --- Columna de la Imagen (Izquierda) --- */
        [data-testid="stHorizontalBlock"] > div:nth-child(1) {{
            padding: 0 !important;
            height: 100vh;
            background: transparent !important;
        }}

        /* Estilo para la imagen dentro de su contenedor (puede omitirse si la imagen es solo bg) */
        [data-testid="stImage"] img {{
            display: none !important; 
        }}

        /* --- Columna del Formulario (Derecha) --- */
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

        /* Responsive: en pantallas pequeñas, ajustar el layout */
        @media (max-width: 768px) {{
            [data-testid="stHorizontalBlock"] > div:nth-child(1) {{
                display: none;
            }}
            [data-testid="stHorizontalBlock"] > div:nth-child(2) {{
                background-color: rgba(255,255,255,0.93);
                backdrop-filter: blur(0px);
            }}
            [data-testid="stHorizontalBlock"] > div:nth-child(2) > div {{
                width: 100%;
                box-shadow: none;
            }}
        }}

        /* Animación de entrada */
        @keyframes fadeIn {{
            from {{opacity: 0; transform: translateY(20px);}}
            to {{opacity: 1; transform: translateY(0);}}
        }}

        /* Estilos adicionales para los elementos del formulario */
        button[data-baseweb="tab"] {{ font-size: 18px !important; }}
        .stButton > button {{ transition: transform 0.2s ease-in-out; }}
        .stButton > button:hover {{ transform: scale(1.02); }}
    </style>
"""

st.markdown(page_bg_img, unsafe_allow_html=True)

# --- INICIALIZACIÓN Y LÓGICA DE AUTENTICACIÓN ---
initialize_aipost_session()
initialize_session_state()

# 1. Revalidar sesión de Supabase
revalidate_aipost_session()

# 2. Intentar procesar parámetros de la URL de OAuth
params_were_processed = process_auth_params()

# 3. Lógica de redirección
# Si los parámetros se procesaron exitosamente, linkedin_auth forzará un rerun o switch_page.
# Si no, procedemos con la lógica normal de la página de login.

# Si el procesamiento de parámetros tuvo éxito, la función ya habrá hecho rerun/switch_page,
# por lo que el código siguiente en este script run no es tan crítico, pero
# esta estructura es robusta para futuras modificaciones.
if params_were_processed:
    # process_auth_params ya se encarga de redirigir o hacer rerun,
    # por lo que no hacemos nada aquí, solo evitamos la redirección de abajo.
    st.switch_page("pages/01_Dashboard.py")
    
# Si el usuario ya está logueado y NO venimos de un callback de OAuth, redirigir.
if is_aipost_logged_in() and not ("auth_provider" in st.query_params):
    st.switch_page("pages/01_Dashboard.py")


# --- LAYOUT DE LA PÁGINA DE LOGIN (solo se muestra si no se ha redirigido) ---
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
                    st.rerun()
                else:
                    st.warning("Por favor, introduce tus credenciales.")
        
        st.divider()
        st.markdown("<p style='text-align: center; color: grey;'>O inicia sesión con</p>", unsafe_allow_html=True)
        linkedin_login_url = f"{FASTAPI_URL}/auth/login/linkedin?create_platform_session=true"
        st.link_button("Iniciar Sesión con LinkedIn", linkedin_login_url, use_container_width=True)

    # --- FORMULARIO DE REGISTRO ---
    with signup_tab:
        with st.form("signup_form"):
            st.text_input("Email", key="signup_email", placeholder="tu@email.com")
            st.text_input("Crea una contraseña", type="password", key="signup_password")
            st.text_input("Confirma tu contraseña", type="password", key="confirm_password")
            st.checkbox("Acepto los Términos y la Política de Privacidad.", key="terms")
            if st.form_submit_button("Crear Cuenta", use_container_width=True, type="primary"):
                if not st.session_state.terms:
                    st.error("Debes aceptar los términos y condiciones.")
                elif st.session_state.signup_password != st.session_state.confirm_password:
                    st.error("Las contraseñas no coinciden.")
                else:
                    signup(st.session_state.signup_email, st.session_state.signup_password)