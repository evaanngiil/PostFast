# auth.py
import streamlit as st
import requests
import json
import base64
from urllib.parse import unquote_plus
from streamlit.components.v1 import html

try: 
    from src.core.constants import FASTAPI_URL
except ImportError: 
    FASTAPI_URL = "http://localhost:8000"
try: 
    from src.core.logger import logger
except ImportError: 
    import logging; logger = logging.getLogger(__name__); logger.warning("Using basic logger.")

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

try:
    from src.social_apis import get_linkedin_organizations, get_linkedin_user_info
    # Si Instagram se añade en el futuro: from src.social_apis import get_instagram_accounts
except ImportError:
    logger.error("Dummy social API funcs used.")
    def get_linkedin_organizations(token): return [{'urn': 'li_dummy_org_1', 'name': 'Dummy LI Org', 'platform': 'LinkedIn', 'id': 'li_dummy_org_1'}]
    # get_linkedin_user_info es crucial, asegurémonos de que exista un dummy válido si falla la importación
    def get_linkedin_user_info(token): return {'sub': 'dummy_user_sub', 'name': 'Dummy User', 'email': 'dummy@example.com', 'picture': None, 'id': 'dummy_user_sub'}


# --- Funciones de inicialización y verificación --
def initialize_session_state():
    defaults = {
        "li_token_data": None, "li_user_info": None, "li_connected": False,
        "user_accounts": {}, "selected_account": None, "auth_error": None,
        "processed_auth_params": False, "session_verified": False
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
    if not isinstance(st.session_state.user_accounts, dict): st.session_state.user_accounts = {}
    if "LinkedIn" not in st.session_state.user_accounts or not isinstance(st.session_state.user_accounts["LinkedIn"], list):
        st.session_state.user_accounts["LinkedIn"] = []

    st.session_state.session_verified = False
    logger.debug("Session state initialized/reset verification flag.")


def verify_session_on_load() -> bool:
    """
    Intenta verificar la sesión existente en st.session_state llamando a /auth/me.
    Actualiza st.session_state si la verificación es exitosa.
    Devuelve True si una sesión válida fue verificada, False en caso contrario.
    """
    if st.session_state.get("session_verified", False):
        logger.debug("Session already verified in this run.")
        return st.session_state.get("li_connected", False) # Solo chequear LI

    logger.debug("Attempting to verify existing session via token...")
    verified = False
    token_to_verify = None

    # Solo chequear LinkedIn
    if st.session_state.get("li_token_data") and st.session_state.li_token_data.get("access_token"):
        token_to_verify = st.session_state.li_token_data["access_token"]
        platform_to_verify = "linkedin" # Única plataforma activa
        logger.debug(f"Found token for {platform_to_verify} in session state. Calling /auth/me for validation...")
        auth_status_url = f"{FASTAPI_URL}/auth/me"
        headers = {'Authorization': f'Bearer {token_to_verify}', 'Accept': 'application/json'}
        try:
            response = requests.get(auth_status_url, headers=headers, timeout=10)
            response.raise_for_status()
            auth_data = response.json()
            logger.debug(f"[/auth/me] response received: {auth_data}") # Log detallado de respuesta

            if auth_data.get("authenticated") and auth_data.get("provider") == "linkedin":
                logger.info(f"Session successfully verified via token for provider: {auth_data.get('provider')}")
                # Actualizar st.session_state con la data fresca del backend
                st.session_state.li_token_data = auth_data.get("token_data")
                st.session_state.li_user_info = auth_data.get("user_info", {})
                st.session_state.li_connected = True 
                st.session_state.auth_error = None
                verified = True
                logger.info("Session state updated: li_connected=True")
            else:
                # Si /auth/me devuelve no autenticado O es de otro provider (no debería pasar)
                logger.warning(f"Token validation via /auth/me failed or wrong provider. Reason: {auth_data.get('reason', 'Unknown')}, Provider: {auth_data.get('provider')}. Clearing local LI session.")
                st.session_state.li_connected = False
                st.session_state.li_token_data = None
                st.session_state.li_user_info = None
                verified = False

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error validating token: {e}")
            st.session_state.li_connected = False
            st.session_state.li_token_data = None
            st.session_state.li_user_info = None
            if e.response.status_code == 401: st.session_state.auth_error = "Sesión inválida/expirada."
            else: st.session_state.auth_error = f"Error servidor ({e.response.status_code})"
            verified = False
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection error validating token: {e}")
            st.session_state.auth_error = "Error conexión servidor auth."
            # No limpiar estado aquí, podría ser temporal
            verified = False # No podemos verificar
        except Exception as e:
            logger.exception("Unexpected error during token validation.")
            st.session_state.li_connected = False # Limpiar por si acaso
            st.session_state.li_token_data = None
            st.session_state.li_user_info = None
            st.session_state.auth_error = f"Error inesperado sesión: {e}"
            verified = False
    else:
        logger.debug("No existing LinkedIn token found in session state to verify.")
        verified = False

    st.session_state.session_verified = True # Marcar como verificado (o intento fallido)
    logger.debug(f"verify_session_on_load finished. Verified status: {verified}, li_connected: {st.session_state.get('li_connected')}")
    return verified


def process_auth_params():
    """
    Checks URL query parameters for auth info after OAuth redirect.
    Run AFTER verify_session_on_load. Only processes if no verified session exists.
    Devuelve True si procesó parámetros exitosamente, False en caso contrario.
    """
    # Solo procesar si no tenemos ya una sesión verificada Y no hemos procesado params antes
    if st.session_state.get("session_verified", False) and (st.session_state.get("fb_connected") or st.session_state.get("li_connected")):
         logger.debug("Skipping URL param processing: Session already verified.")
         return False
    if st.session_state.get("processed_auth_params", False):
        logger.debug("Skipping URL param processing: Params already processed in this session.")
        return False

    processed_successfully = False
    query_params = st.query_params
    auth_provider = query_params.get("auth_provider")
    auth_token_encoded = query_params.get("auth_token")
    user_info_b64 = query_params.get("user_info")
    auth_error = query_params.get("auth_error")

    # Procesar error primero
    if auth_error:
        logger.error(f"Auth error received from callback URL: {auth_error}")
        st.session_state.auth_error = f"Error de autenticación: {auth_error}"
        st.query_params.clear()
        st.session_state.processed_auth_params = True
        return False # Hubo error

    # Procesar datos de autenticación si existen
    if auth_provider and auth_token_encoded and user_info_b64:
        logger.info(f"Auth parameters found in URL for provider: {auth_provider}. Processing...")
        try:
            access_token = unquote_plus(auth_token_encoded)
            user_info_json = base64.urlsafe_b64decode(user_info_b64).decode()
            user_info = json.loads(user_info_json)
            token_data = {"access_token": access_token} # Estructura básica

            if auth_provider == "facebook":
                st.session_state.fb_token_data = token_data
                st.session_state.fb_user_info = user_info
                st.session_state.fb_connected = True
                logger.info("Facebook session established from URL params.")
            elif auth_provider == "linkedin":
                st.session_state.li_token_data = token_data
                st.session_state.li_user_info = user_info
                st.session_state.li_connected = True
                logger.info("LinkedIn session established from URL params.")
            else:
                logger.warning(f"Unknown auth provider in URL params: {auth_provider}")
                st.session_state.auth_error = f"Proveedor desconocido: {auth_provider}"

            st.query_params.clear() # Limpiar URL
            st.session_state.processed_auth_params = True # Marcar como procesado
            st.session_state.session_verified = True # Marcar como verificado también
            processed_successfully = True
            logger.debug("Auth URL parameters processed and cleared.")
            logger.debug(f"process_auth_params finished. li_connected: {st.session_state.get('li_connected')}")
            # No hacer rerun aquí, dejar que app.py continúe y cargue cuentas si es necesario

        except Exception as e:
            logger.exception("Error processing auth params from URL.")
            st.session_state.auth_error = "Error procesando datos de autenticación."
            st.query_params.clear()
            st.session_state.processed_auth_params = True # Marcar igual para no reintentar
            processed_successfully = False
    else:
        logger.debug("No auth parameters found in URL.")

    return processed_successfully


def load_user_accounts(platform: str) -> bool:
    """
    Loads user's own profile and any managed organizations/pages.
    For LinkedIn, includes the user's profile and organizations.
    """
    if platform != "LinkedIn":
        logger.warning(f"Account loading only implemented for LinkedIn, requested for {platform}")
        return False

    is_connected = st.session_state.get("li_connected", False)
    token_dict = st.session_state.get("li_token_data")
    user_info = st.session_state.get("li_user_info") # Necesitamos user info para el perfil

    if not is_connected or not token_dict or not user_info:
        logger.warning("Cannot load accounts for LinkedIn: Not connected, no token, or no user info.")
        return False

    user_access_token = token_dict.get("access_token")
    user_profile_id = user_info.get("sub") # El ID ('sub') del usuario
    user_profile_name = user_info.get("name", "Your Profile")

    if not user_access_token or not user_profile_id:
        logger.error("Cannot load accounts for LinkedIn: Access token or User ID (sub) missing.")
        return False

    logger.info(f"Loading accounts for {platform}...")
    accounts_list = []
    success = False

    # 1. Añadir el perfil personal del usuario como una "cuenta" seleccionable
    accounts_list.append({
        "id": f"urn:li:person:{user_profile_id}", # Usar el URN de persona como ID
        "urn": f"urn:li:person:{user_profile_id}",
        "name": f"{user_profile_name} (Personal Profile)",
        "platform": "LinkedIn",
        "type": "profile" # Añadir tipo para distinguir
    })
    logger.debug(f"Added personal profile to account list: {accounts_list[0]['name']}")

    # 2. Intentar cargar organizaciones administradas (como antes)
    try:
        logger.debug("Calling API for LinkedIn organizations...")
        api_result = get_linkedin_organizations(user_access_token) # Esta función ya devuelve lista de dicts con 'urn', 'name', 'platform'
        if api_result is not None:
            logger.debug(f"Received {len(api_result)} LI organizations from API.")
            # Añadir tipo 'organization' y asegurar 'id'
            for org in api_result:
                org['type'] = 'organization'
                if 'urn' not in org and 'id' in org: 
                    org['urn'] = org['id'] # Asegurar URN
                elif 'id' not in org and 'urn' in org: 
                    org['id'] = org['urn'] # Asegurar ID

                accounts_list.append(org)
            success = True # Considerar éxito si al menos el perfil se añadió
        else:
            logger.warning("get_linkedin_organizations returned None or failed, only personal profile available.")
            success = True # Aún así es éxito porque tenemos el perfil personal

    except Exception as e:
        logger.exception(f"Failed loading LinkedIn organizations due to exception: {e}")
        st.error(f"Error cargando organizaciones de LinkedIn: {e}")
        # No fallar aquí, continuar con el perfil personal si ya se añadió
        success = True if accounts_list else False # Éxito si al menos el perfil está

    # Actualizar st.session_state
    if success:
        if not isinstance(st.session_state.user_accounts, dict): st.session_state.user_accounts = {}
        st.session_state.user_accounts[platform] = accounts_list
        logger.info(f"Successfully loaded {len(accounts_list)} account(s) (profile/orgs) for {platform} into session state.")
        # Seleccionar el perfil personal por defecto si no hay nada seleccionado
        if st.session_state.get("selected_account") is None and accounts_list:
             st.session_state.selected_account = accounts_list[0] # Seleccionar el perfil personal
             logger.info(f"Default account selected: {accounts_list[0]['name']}")

    else:
        logger.error(f"Failed to load any accounts (including personal profile) for {platform}.")
        if isinstance(st.session_state.user_accounts, dict): st.session_state.user_accounts[platform] = []

    return success

def display_auth_status(sidebar: bool = True):
    """Display auth status, user info, and disconnect button below profile info."""
    container = st.sidebar if sidebar else st

    # --- Sección Superior: Información del Usuario y Disconnect ---
    if st.session_state.get("li_connected"):
        user_info = st.session_state.get("li_user_info")
        profile_pic_url = None
        display_name = "LinkedIn User"

        if user_info:
            display_name = user_info.get('name', display_name)
            profile_pic_url = user_info.get('picture')
            logger.debug(f"User Info for display: Name='{display_name}', Pic URL='{profile_pic_url}'")

        # Col 1: Imagen, Col 2: Nombre/Caption
        col_img, col_info = container.columns([1, 4]) # Ratio ajustado

        with col_img:
            if profile_pic_url:
                st.image(profile_pic_url, width=50, use_container_width=False)
            else:
                st.markdown("👤", unsafe_allow_html=True) # Icono

        with col_info:
            st.markdown(f"**{display_name}**", help="Logged in user") # Añadir tooltip
            st.caption("Connected via LinkedIn")

        # Botón Disconnect ABAJO de la info, ocupando el ancho disponible
        if container.button("Disconnect", key="disconnect_li_below_btn", help="Log out from LinkedIn", type="secondary", use_container_width=True):
            # ... (lógica de limpieza de session_state como antes) ...
            st.session_state.li_connected = False
            st.session_state.li_token_data = None
            st.session_state.li_user_info = None
            st.session_state.user_accounts.pop("LinkedIn", None)
            st.session_state.selected_account = None
            st.session_state.auth_error = None
            st.session_state.processed_auth_params = False
            st.session_state.session_verified = False
            logger.info("User initiated disconnect.")
            logout_url = f"{FASTAPI_URL}/auth/logout"
            # Usar meta refresh para la redirección
            st.markdown(f'<meta http-equiv="refresh" content="0; url={logout_url}">', unsafe_allow_html=True)
            st.stop()

        container.divider() # Separador después del bloque de usuario conectado

    # --- Sección Inferior: Botón Connect (si no está conectado) ---
    else:
        container.subheader("🔗 Connections")
        if st.session_state.get("auth_error"):
            st.error(st.session_state.auth_error)
            st.session_state.auth_error = None

        li_login_url = f"{FASTAPI_URL}/auth/login/linkedin"
        # Usar link_button (sin key)
        container.link_button("Connect with LinkedIn", li_login_url)


def display_account_selector(sidebar: bool = True):
    """Displays selector for LinkedIn Profile/Organizations, or just confirms profile."""
    container = st.sidebar if sidebar else st

    # Verificar conexión a LinkedIn
    if not st.session_state.get("li_connected"):
        container.info("Connect to LinkedIn to select an account.")
        return None

    # Obtener cuentas cargadas para LinkedIn
    user_accounts_dict = st.session_state.get("user_accounts", {})
    linkedin_accounts = []
    if isinstance(user_accounts_dict, dict):
        accounts = user_accounts_dict.get("LinkedIn", [])
        if isinstance(accounts, list):
            linkedin_accounts = accounts
        else: logger.warning("LinkedIn accounts data is not a list.")
    else: logger.warning("user_accounts is not a dictionary.")

    # Si no hay cuentas (ni siquiera el perfil, lo cual sería un error en load_user_accounts)
    if not linkedin_accounts:
        container.warning("No LinkedIn profile or organizations found/loaded.")
        if st.session_state.get("selected_account"): st.session_state.selected_account = None
        return None

    container.subheader("🎯 Active Account")

    # Si SÓLO está el perfil personal
    if len(linkedin_accounts) == 1 and linkedin_accounts[0].get("type") == "profile":
        profile_info = linkedin_accounts[0]
        container.info(f"Using: **{profile_info.get('name', 'Your Profile')}**")
        # Asegurar que está seleccionado en session_state
        if st.session_state.get("selected_account") != profile_info:
             st.session_state.selected_account = profile_info
             # No hacer rerun aquí para evitar bucles si algo más cambia
        return st.session_state.selected_account

    # Si hay MÚLTIPLES cuentas (perfil + orgs)
    else:
        def format_account_option(account):
            if account is None: return "Select Account..."
            name = account.get('name', '?')
            acc_type = account.get('type', 'unknown').capitalize()
            # Simplificar nombre si es el perfil personal
            if acc_type == 'Profile': name = name.replace(" (Personal Profile)", "")
            return f"{name} ({acc_type})"

        options_list = [None] + linkedin_accounts # [None] para la opción "Select..."
        currently_selected = st.session_state.get("selected_account")
        current_index = 0

        # Encontrar índice del seleccionado actualmente (usando ID/URN)
        if currently_selected and isinstance(currently_selected, dict) and currently_selected.get("platform") == "LinkedIn":
            current_id = currently_selected.get('id')
            try:
                current_index = next(i for i, acc in enumerate(options_list) if acc and acc.get('id') == current_id)
            except StopIteration:
                logger.warning(f"Previously selected account ID {current_id} not found in options. Resetting.")
                st.session_state.selected_account = None; current_index = 0
        elif not currently_selected and linkedin_accounts: # Si no hay selección previa, seleccionar el perfil (índice 1 porque 0 es None)
             if linkedin_accounts[0].get("type") == "profile":
                  current_index = 1
                  st.session_state.selected_account = linkedin_accounts[0] # Establecer selección inicial

        selected_index = container.selectbox(
            label="Select Account to Use",
            options=range(len(options_list)),
            format_func=lambda i: format_account_option(options_list[i]),
            index=current_index, key="linkedin_account_selector",
            help="Choose your personal profile or an organization to interact with."
        )
        newly_selected = options_list[selected_index]

        # Actualizar estado si la selección cambió
        current_sel_id = st.session_state.get("selected_account", {}).get('id') if isinstance(st.session_state.get("selected_account"), dict) else None
        new_sel_id = newly_selected.get('id') if isinstance(newly_selected, dict) else None

        if new_sel_id != current_sel_id:
            st.session_state.selected_account = newly_selected
            logger.info(f"Account selection changed to: {format_account_option(newly_selected)}" if newly_selected else "Account selection cleared.")
            st.rerun() # Rerun para que el resto de la app use la nueva cuenta

        return st.session_state.get("selected_account")

# OAuth2 scheme for Bearer token authentication in API endpoints
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # "token" es un placeholder, no lo usaremos directamente

async def get_current_session_data_from_token(token: str = Depends(oauth2_scheme)):
    """
    Dependency to verify Bearer token and fetch session data.
    Esto se usará en los endpoints de API (analytics, content).
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=503, detail="Database unavailable")

        # Buscar la sesión usando el ACCESS TOKEN
        # Si los tokens cambian (refresh), esto podría fallar.
        # Una mejor aproximación sería validar el token con el proveedor O usar el session_cookie_id si estuviera disponible.
        # Por simplicidad ahora, buscamos por access_token. NOTE: Considerar alternativas.
        result = conn.execute("""
            SELECT session_cookie_id, provider, user_provider_id, access_token, refresh_token,
                   token_type, expires_at, user_info
            FROM user_sessions
            WHERE access_token = ?
        """, [token]).fetchone() # ¡CUIDADO! Buscar por token puede no ser ideal si refrescan.

        if not result:
            logger.warning(f"Bearer token provided but no matching session found.")
            raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

        (session_cookie_id, provider, user_pid, access_token_db, refresh_token,
         t_type, expires_at, user_info_json) = result

        # Validar si el token ha expirado (si expires_at está presente)
        if expires_at and isinstance(expires_at, datetime) and datetime.now(timezone.utc) > expires_at:
             logger.warning(f"Token expired for session {session_cookie_id}")
             # Aquí podríamos intentar refrescar el token si tuviéramos el refresh_token
             raise HTTPException(status_code=401, detail="Token expired", headers={"WWW-Authenticate": "Bearer"})

        # Actualizar last_accessed_at
        conn.execute("UPDATE user_sessions SET last_accessed_at = current_timestamp WHERE session_cookie_id = ?", [session_cookie_id])

        user_info = json.loads(user_info_json) if user_info_json else {}

        # Devolver datos relevantes para el endpoint
        return {
            "session_cookie_id": session_cookie_id,
            "provider": provider,
            "user_provider_id": user_pid,
            "access_token": access_token_db,
            "refresh_token": refresh_token,
            "token_type": t_type,
            "expires_at": expires_at,
            "user_info": user_info,
            "token_data": { # Para consistencia con lo que espera Streamlit
                "access_token": access_token_db,
                "refresh_token": refresh_token,
                "token_type": t_type,
                "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at
            }
        }

    except HTTPException as http_exc:
        raise http_exc # Re-lanzar excepciones HTTP
    except Exception as e:
        logger.exception(f"Error verifying bearer token: {e}")
        raise HTTPException(status_code=500, detail="Error verifying token")
    finally:
        if conn: conn.close()