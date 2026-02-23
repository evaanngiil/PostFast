import streamlit as st
import os
import requests
import json
import base64
import requests.sessions
from urllib.parse import unquote_plus
from streamlit_cookies_controller import CookieController

from src.services.supabase_client import get_supabase
from src.supabase_auth import (
    revalidate_aipost_session,
    mark_aipost_logged_in,
    is_aipost_logged_in,
)

try:
    from src.core.constants import FASTAPI_URL, SECRET_KEY
except ImportError:
    FASTAPI_URL = "http://localhost:8000"

try:
    from src.core.logger import logger
except ImportError:
    import logging; logger = logging.getLogger(__name__); logger.warning("Using basic logger.")

try:
    from src.social_apis import get_linkedin_organizations
except ImportError:
    logger.error("Dummy social API funcs used.")
    def get_linkedin_organizations(token): return []


def get_cookie_controller():
    """
    Inicializa el controlador de cookies solo cuando se llama, 
    evitando que se ejecute al importar el módulo y rompa set_page_config.
    """
    return CookieController(key=SECRET_KEY)

# ----------------- INICIALIZADORES / HELPERS -----------------

def initialize_session_state():
    """Inicializa el session_state con valores por defecto si no existen."""
    defaults = {
        'aipost_logged_in': False, 'user': None, 'aipost_session_revalidated': False,
        'li_connected': False, 'li_user_info': None, 'li_token_data': None,
        'user_accounts': {}, 'LinkedIn_accounts_loaded_flag': False,
        'session_verified': False, 'auth_error': None, 'selected_account': None,
        'auth_token_for_url': None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def ensure_session_initialized(force=False):
    """Inicializa y valida la sesión en el orden correcto."""
    # La inicialización debe ocurrir en cada página, no aquí.
    if not st.session_state.get('session_revalidated', False) or force:
        revalidate_aipost_session()

    if not process_auth_params():
        # Si no se procesaron parámetros, intentar verificar una sesión existente
        verify_session_on_load()

    if st.session_state.get('li_connected') and not st.session_state.get('LinkedIn_accounts_loaded_flag'):
        load_user_accounts()
    return True


def verify_session_on_load() -> bool:
    if st.session_state.get("li_connected"):
        return True

    logger.debug("Attempting to verify existing session via /auth/me...")
    auth_status_url = f"{FASTAPI_URL}/auth/me"
    headers = {'Accept': 'application/json'}

    try:
        # 1) Preferir token guardado en session_state
        li_token_data = st.session_state.get("li_token_data") or {}
        token = li_token_data.get("access_token") if isinstance(li_token_data, dict) else None

        # 2) FALLBACK: si no hay token en session_state, comprobar query params (útil justo después de la redirección)
        if not token:
            qp = st.query_params
            token_q = qp.get("auth_token", [None])[0]
            if token_q:
                token = unquote_plus(token_q)
                st.session_state.li_token_data = {"access_token": token}
                logger.debug("[verify_session_on_load] token recovered from query_params and stored in session_state")

        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.debug("[verify_session_on_load] Adding Authorization header for /auth/me")

        with requests.sessions.Session() as session:
            resp = session.get(auth_status_url, headers=headers, timeout=10)
            try:
                auth_data = resp.json() if resp.ok else {"authenticated": False}
            except ValueError:
                logger.warning("[verify_session_on_load] /auth/me returned non-json response")
                auth_data = {"authenticated": False}

        logger.debug(f"[verify_session_on_load] /auth/me status_code={resp.status_code} auth_data={auth_data}")

        if isinstance(auth_data, dict) and auth_data.get("authenticated"):
            if auth_data.get("provider") == "linkedin":
                st.session_state.li_token_data = auth_data.get("token_data") or st.session_state.get("li_token_data") or {}
                st.session_state.li_user_info = auth_data.get("user_info") or st.session_state.get("li_user_info") or {}
                st.session_state.li_connected = True
                st.session_state.session_verified = True
                logger.info("LinkedIn session restored from backend (via /auth/me).")
                return True
    except Exception as e:
        logger.error(f"Error during /auth/me call: {e}", exc_info=True)

    return False

def process_auth_params() -> bool:
    """
    Procesa los parámetros de la URL DESPUÉS del callback de OAuth.
    Devuelve True si se procesaron parámetros, para que ensure_auth se detenga.
    """
    query_params = st.query_params
    auth_provider = query_params.get("auth_provider")

    if not auth_provider:
        return False # No hay nada que procesar

    logger.debug(f"Processing auth params from URL for provider: {auth_provider}")
    
    # Extraemos todos los datos de la URL
    auth_token_encoded = query_params.get("auth_token")
    user_info_b64 = query_params.get("user_info")
    create_platform_session = query_params.get("create_platform_session")
    auth_error = query_params.get("auth_error")

    # Siempre limpiamos los parámetros para evitar bucles
    try:
        st.query_params.clear()
    except Exception:
        pass
    
    # Manejo de errores desde el backend
    if auth_error:
        st.session_state.auth_error = f"Error de autenticación: {auth_error}"
        st.rerun()
        return True

    # Si tenemos un proveedor y un token, procesamos el login
    if auth_provider == "linkedin" and auth_token_encoded:
        try:
            # 1. Decodificar y guardar los datos de LinkedIn en session_state
            access_token = unquote_plus(auth_token_encoded)
            st.session_state.li_token_data = {"access_token": access_token}
            
            user_info_json = base64.urlsafe_b64decode(user_info_b64.encode() + b'==').decode()
            user_info = json.loads(user_info_json)
            
            logger.debug(f"Decoded LinkedIn user info: {user_info}")
            st.session_state.li_user_info = user_info
            
            # 2. MARCAR SIEMPRE COMO CONECTADO A LINKEDIN
            st.session_state.li_connected = True
            st.session_state.session_verified = True
            logger.info("LinkedIn session established from URL params.")

            # 3. Lógica específica para la sesión de la plataforma (AIPost)
            if create_platform_session == "true":
                # Si venimos del botón "Iniciar Sesión con LinkedIn", creamos/validamos la sesión de AIPost
                email = user_info.get('email')
                name = user_info.get('name', 'Usuario LinkedIn')

                # Use the LinkedIn user ID ('id' or 'sub') for the MockUser id
                user_id = user_info.get('id') or user_info.get('sub')

                if email and user_id:
                    # Simula la creación de un objeto User para marcar el login en AIPost
                    mock_user = type('MockUser', (), {
                        'id': user_id,
                        'email': email,
                        'name': name,
                        'user_metadata': {'name': name, 'email': email}
                    })()
                    mark_aipost_logged_in(mock_user)
                    logger.info(f"AIPost platform session created/validated for {email}")

                # Handle cases where email or id might be missing from LinkedIn info
                elif not user_id:
                     st.session_state.auth_error = "No se pudo obtener el ID de usuario de LinkedIn para iniciar sesión."
                     st.session_state.li_connected = False # Revert connection if essential info missing

                elif not email:
                    st.session_state.auth_error = "No se pudo obtener el email de LinkedIn para iniciar sesión."

            # 4. Redirigir al Dashboard
            st.switch_page("pages/Dashboard.py")
            
        except Exception as e:
            st.session_state.auth_error = "Error procesando datos de autenticación."
            logger.exception(f"Failed to process auth params: {e}")
            st.rerun() # Hacemos rerun para mostrar el error

    return True # Indicamos que se procesaron parámetros

# ----------------- FUNCIONES PRINCIPALES -----------------
def load_user_accounts():
    """Carga las cuentas de usuario (perfil, páginas) para LinkedIn."""
    
    if st.session_state.get('LinkedIn_accounts_loaded_flag') or not st.session_state.get("li_connected"):
        return

    token = st.session_state.get('auth_token_for_url')
    user_info = st.session_state.get("li_user_info", {})
    user_profile_id = user_info.get("sub")

    if not token or not user_profile_id:
        return

    logger.info("Loading LinkedIn accounts...")
    accounts_list = [
        {
            "id": f"urn:li:person:{user_profile_id}",
            "urn": f"urn:li:person:{user_profile_id}",
            "name": user_info.get("name", "Tu Perfil"),
            "platform": "LinkedIn",
            "type": "profile",
            "logo": {"picture": user_info.get("picture")}
        }
    ]

    try:
        managed_orgs = get_linkedin_organizations(token)
        if isinstance(managed_orgs, list):
            accounts_list.extend(managed_orgs)
    except Exception as e:
        logger.exception(f"Failed loading LinkedIn organizations: {e}")

    st.session_state.user_accounts = accounts_list
    if not st.session_state.get("selected_account") and accounts_list:
        st.session_state.selected_account = accounts_list[0]
        
    st.session_state.LinkedIn_accounts_loaded_flag = True
    logger.info(f"Loaded {len(accounts_list)} LinkedIn accounts.")


def _restore_session_from_api(token: str) -> bool:
    """Usa un token para llamar a /auth/me y repoblar st.session_state."""
    if not token: return False
        
    logger.debug("Attempting to restore session from API via /auth/me")
    auth_status_url = f"{FASTAPI_URL}/auth/me"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(auth_status_url, headers=headers, timeout=10)
        if resp.ok:
            auth_data = resp.json()
            if auth_data.get("authenticated"):
                provider = auth_data.get("provider")
                user_info = auth_data.get("user_info", {})
                
                # Poblar estado de la plataforma AIPost
                st.session_state.aipost_logged_in = True
                user_data_for_mock = {'user_metadata': user_info, 'email': user_info.get('email'), 'name': user_info.get('name')}
                st.session_state.user = type('MockUser', (), user_data_for_mock)()
                
                # Guardar el token para la navegación futura
                st.session_state.auth_token_for_url = token

                if provider == "linkedin":
                    st.session_state.li_user_info = user_info
                    st.session_state.li_connected = True
                
                st.session_state.session_verified = True
                logger.info(f"✅ Session restored from API for provider: {provider}")
                return True
        else:
            logger.warning(f"API rejected token. Status: {resp.status_code}")
            st.session_state.auth_error = "Tu sesión ha expirado o es inválida."
            
    except Exception as e:
        logger.error(f"Error during API session restoration: {e}")
        st.session_state.auth_error = "Error de conexión al verificar la sesión."

    # Limpiar estado si la restauración falla
    st.session_state.li_connected = False
    st.session_state.aipost_logged_in = False
    st.session_state.auth_token_for_url = None
    return False


def ensure_auth(protect_route: bool = True):
    """
    Función central de autenticación. Debe ser llamada al inicio de CADA página.
    Verifica si el usuario está logueado y si no, intenta restaurar la sesión.
    Si protect_route es True, redirige al usuario a la página de inicio si no está logueado.
    """
    # initialize_session_state()
    cookies = get_cookie_controller()

    # 1. Si la sesión ya está verificada en esta ejecución, no hacemos nada más.
    if st.session_state.get('session_verified'):
        return

    # 2. Revalidar la sesión de Supabase si existe (sincroniza el estado local de Supabase)
    revalidate_aipost_session()
    
    if protect_route and not st.session_state.get('aipost_logged_in'):
        st.warning("Debes iniciar sesión para acceder a esta página.")
        st.switch_page("app.py")
        st.stop()

    # 3. Intentar restaurar la sesión usando un token, ya sea de la URL o del estado de sesión.
    token = st.query_params.get("auth_token") or st.session_state.get('auth_token_for_url')
    logger.debug(f"[ensure_auth] auth_token from URL or session_state: {'PRESENT' if token else 'NOT PRESENT'}")

    if  token is not None:
        try:
            cookies.set("linkedin_access_token", token, max_age=7 * 24 * 60 * 60) # 7 días
        except Exception as e:
            logger.warning(f"No se pudo establecer la cookie: {e}")
    else:
        # Si NO tenemos token en memoria, intentamos leer la cookie
        # _ = cookies.getAll()
        token = cookies.get("linkedin_access_token")
        if token:
            st.session_state.li_token_data = {"access_token": token}
            st.session_state.auth_token_for_url = token
            logger.debug("[ensure_auth] auth_token recovered from cookies and stored in session_state")
    
    if token:
        logger.debug(f"[ensure_auth] TOKEN: {token}")
        if _restore_session_from_api(token):
            # Limpiamos el token de la URL para tener una URL más limpia
            if "auth_token" in st.query_params:
                st.query_params.clear()
            # Si la restauración fue exitosa, cargamos las cuentas y terminamos.
            load_user_accounts()
            return

    # 4. Procesar el callback de OAuth de LinkedIn (solo ocurre una vez después del login)
    # Esto es para el flujo de conexión inicial con LinkedIn.
    if "auth_provider" in st.query_params and st.query_params.get("auth_provider") == "linkedin":
        token_from_url = st.query_params.get("auth_token")
        if token_from_url:
            st.session_state.auth_token_for_url = token_from_url
            st.query_params.clear() # Limpiamos para evitar bucles
            # Forzamos un rerun para que el flujo de restauración de arriba se active con el nuevo token
            st.rerun()



# ----------------- FUNCIONES UI AUXILIARES -----------------
def display_auth_status(sidebar: bool = True):
    container = st.sidebar if sidebar else st
    if not is_aipost_logged_in():
        container.info("Inicia sesión en AIPost para conectar redes sociales.")
        return

    logger.warning(f"[auth-status] Displaying auth status UI Sidebar{st.session_state}")

    if st.session_state.get("li_connected"):
        logger.debug("HAY CONEXIÓN A LINKEDIN - mostrando estado en sidebar")
        
        user_info = st.session_state.get("li_user_info")
        display_name, profile_pic_url = "Usuario LinkedIn", None
        if isinstance(user_info, dict):
            display_name = user_info.get('name', display_name)
            profile_pic_url = user_info.get('picture')
        
        col_img, col_info = container.columns([1, 4])
        with col_img:
            if profile_pic_url: 
                st.image(profile_pic_url, width=45)
            else: 
                st.markdown("👤", unsafe_allow_html=True)
                
        with col_info:
            st.markdown(f"**{display_name}**")
            st.caption("Conectado a LinkedIn")

        if container.button("Desconectar LinkedIn", key="disconnect_li_btn", use_container_width=True):
            cookies.remove("linkedin_access_token")

            st.session_state.li_connected = False
            st.session_state.li_token_data = None
            st.session_state.li_user_info = None
            if isinstance(st.session_state.get("user_accounts"), dict):
                st.session_state.user_accounts.pop("LinkedIn", None)
            st.session_state.selected_account = None
            try: 
                requests.get(f"{FASTAPI_URL}/auth/logout", timeout=5)
                logger.info("Llamada al endpoint de logout del backend realizada.")
            except Exception: 
                pass
            st.rerun()
    else:
        if st.session_state.get("auth_error"):
            container.error(st.session_state.auth_error)
            st.session_state.auth_error = None
        
        container.link_button("🔗 Conectar LinkedIn", f"{FASTAPI_URL}/auth/login/linkedin", use_container_width=True)

def display_account_selector(sidebar: bool = True):
    container = st.sidebar if sidebar else st
    if not st.session_state.get("li_connected"):
        container.info("Conecta LinkedIn para seleccionar una cuenta.")
        return None

    linkedin_accounts = (st.session_state.get("user_accounts") or {})
    if not linkedin_accounts:
        container.warning("No se encontraron perfiles de LinkedIn.")
        return None

    container.subheader("🎯 Cuenta Activa")
    
    if len(linkedin_accounts) == 1:
        profile_info = linkedin_accounts[0]
        container.info(f"Usando: **{profile_info.get('name', 'Tu Perfil')}**")
        st.session_state.selected_account = profile_info
        return profile_info
    else:
        def format_option(acc):
            return f"{acc.get('name', 'N/A')} ({acc.get('type', 'N/A').capitalize()})"
        
        current_urn = (st.session_state.get("selected_account") or {}).get('urn')
        try:
            current_index = [acc.get('urn') for acc in linkedin_accounts].index(current_urn)
        except (ValueError, AttributeError):
            current_index = 0
            st.session_state.selected_account = linkedin_accounts[0]

        selected_index = container.selectbox(
            "Selecciona un Perfil u Organización",
            options=range(len(linkedin_accounts)),
            format_func=lambda i: format_option(linkedin_accounts[i]),
            index=current_index,
            key="linkedin_account_selector"
        )
        
        newly_selected_account = linkedin_accounts[selected_index]
        if (st.session_state.selected_account or {}).get('urn') != newly_selected_account.get('urn'):
            st.session_state.selected_account = newly_selected_account
            st.rerun()

        return st.session_state.selected_account