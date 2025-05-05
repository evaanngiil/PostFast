# auth.py
import streamlit as st
import requests
import json
import base64
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from urllib.parse import unquote_plus
from requests_oauthlib import OAuth2Session
from typing import Optional # Para Optional Header
from streamlit.components.v1 import html
from src.data_processing import get_db_connection

try: 
    from src.core.constants import FASTAPI_URL, DATABASE_URL
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


# Esquema de seguridad para obtener token Bearer de la cabecera Authorization
# tokenUrl es nominal, no lo usamos para obtener el token, solo para decirle a FastAPI cómo extraerlo
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False) # auto_error=False para manejar 401 manualmente

def get_db_connection():
    """Obtiene una conexión síncrona a PostgreSQL."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL is not configured.")
        return None
    try:
        # Usar conexión síncrona
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        logger.debug("PostgreSQL sync connection opened (from auth.py).")
        return conn
    except psycopg.Error as e:
        logger.error(f"Failed to connect sync to PostgreSQL DB (from auth.py): {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting sync to PostgreSQL (from auth.py): {e}", exc_info=True)
        return None


def get_current_session_data_from_token(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """
    Dependency (sync): Valida Bearer token, comprueba expiración, devuelve datos.
    Usa psycopg síncrono y maneja resultados dict_row.
    """
    if token is None:
        logger.warning("[Dependency] Auth required: No token provided.")
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})

    conn = None
    cur = None
    try:
        conn = get_db_connection() # Obtener conexión síncrona
        if not conn:
            logger.error("[Dependency] DB connection failed.")
            raise HTTPException(status_code=503, detail="Database service unavailable")

        cur = conn.cursor() # Crear cursor síncrono

        # Usar placeholders %s
        cur.execute("""
            SELECT provider, user_provider_id, access_token, refresh_token,
                   token_type, expires_at, user_info, session_cookie_id
            FROM user_sessions WHERE access_token = %s
        """, (token,))
        result = cur.fetchone() # fetchone() devuelve dict o None

        if not result:
            logger.warning(f"[Dependency] Token validation failed: Token '{token[:5]}...' not found in DB.")
            raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})

        # 'result' es un diccionario
        session_cookie_id = result.get('session_cookie_id') # Usar .get() para seguridad
        expires_at_db = result.get('expires_at')
        user_info_db = result.get('user_info') # Esto es lo que devuelve la DB (JSONB/dict)

        # --- Chequeo de Expiración ---
        token_expired = False
        if expires_at_db:
            expires_at_aware = None
            if isinstance(expires_at_db, datetime):
                if expires_at_db.tzinfo is None: expires_at_aware = expires_at_db.replace(tzinfo=timezone.utc)
                else: expires_at_aware = expires_at_db
            else: logger.warning(f"[Dependency] expires_at is not datetime: {expires_at_db}")
            if expires_at_aware and datetime.now(timezone.utc) > expires_at_aware: token_expired = True
        # ---

        if token_expired:
            logger.warning(f"[Dependency] Access token expired for session {session_cookie_id}.")
            raise HTTPException(status_code=401, detail="Token expired", headers={"WWW-Authenticate": "Bearer"})

        # --- Opcional: Eliminar UPDATE last_accessed_at ---
        # try:
        #     cur.execute("UPDATE user_sessions SET last_accessed_at = current_timestamp WHERE session_cookie_id = %s", (session_cookie_id,))
        #     conn.commit()
        # except psycopg.Error as update_err:
        #     logger.error(f"[Dependency] Failed to update last_accessed_at: {update_err}")
        #     if conn: conn.rollback()
        # -------------------------------------------------

        # Preparar datos de salida
        # user_info_db ya debería ser un dict si es JSONB y row_factory=dict_row funciona
        user_info_out = user_info_db if isinstance(user_info_db, dict) else {}
        # Intentar decodificar solo si NO es un dict (por si acaso)
        if not isinstance(user_info_db, dict) and user_info_db is not None:
             try:
                 user_info_out = json.loads(user_info_db)
             except (json.JSONDecodeError, TypeError) as json_err:
                 logger.warning(f"[Dependency] Could not decode user_info from DB: {json_err}. DB value: {user_info_db}")
                 user_info_out = {}


        session_data = {
            "authenticated": True,
            "provider": result.get('provider'), # Usar .get()
            "user_info": user_info_out,
            "user_provider_id": result.get('user_provider_id'),
            "session_cookie_id": session_cookie_id,
            "token_data": {
                "access_token": result.get('access_token'),
                "refresh_token": result.get('refresh_token'),
                "token_type": result.get('token_type'),
                "expires_at": expires_at_db.isoformat() if isinstance(expires_at_db, datetime) else None
            }
        }
        logger.debug(f"[Dependency] Token validated successfully for {session_data['provider']} user {session_data['user_provider_id']}")
        return session_data

    except HTTPException as http_exc:
        if conn: 
            conn.rollback() # Deshacer transacción en errores HTTP
        raise http_exc
    except psycopg.Error as db_err:
        logger.exception(f"[Dependency] PostgreSQL error verifying token: {db_err}")
        if conn: 
            conn.rollback()
        raise HTTPException(status_code=503, detail="Database error during authentication")
    except Exception as e:
        logger.exception(f"[Dependency] Unexpected error verifying token: {e}")
        if conn: 
            conn.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
         # Cerrar cursor y conexión síncronos
         if cur: 
            cur.close()
         if conn: 
            conn.close()
         logger.debug("[Dependency] PostgreSQL sync connection closed.")

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
            logger.info(f"[/auth/me] response received: {response.text}") # Log de datos de autenticación

            if isinstance(auth_data, dict) and auth_data.get("authenticated") and auth_data.get("provider") == "linkedin":
                 logger.info(f"Session successfully verified via /auth/me for provider: {auth_data.get('provider')}")
                 st.session_state.li_token_data = auth_data.get("token_data")
                 # Asegurarse que user_info es un dict
                 user_info = auth_data.get("user_info")
                 st.session_state.li_user_info = user_info if isinstance(user_info, dict) else {}
                 st.session_state.li_connected = True
                 st.session_state.auth_error = None
                 verified = True
                 logger.info("Local session state updated: li_connected=True")
            else:
                 # El log que veías antes se origina aquí porque auth_data venía corrupto
                 logger.warning(f"Token validation via /auth/me failed or wrong provider. Auth Data: {auth_data}. Clearing local LI session.")
                 st.session_state.li_connected = False; st.session_state.li_token_data = None; st.session_state.li_user_info = None
                 verified = False
        except requests.exceptions.HTTPError as e:
             logger.error(f"HTTP error validating token via /auth/me: {e}")
             st.session_state.li_connected = False; st.session_state.li_token_data = None; st.session_state.li_user_info = None
             if e.response and e.response.status_code == 401: st.session_state.auth_error = "Sesión inválida/expirada."
             elif e.response and e.response.status_code == 503: st.session_state.auth_error = "Servicio no disponible (DB?)."
             else: st.session_state.auth_error = f"Error servidor ({e.response.status_code if e.response else 'N/A'})"
             verified = False
        except requests.exceptions.RequestException as e:
             logger.error(f"Connection error validating token via /auth/me: {e}")
             st.session_state.auth_error = "Error conexión servidor auth."; verified = False
        except Exception as e:
             logger.exception("Unexpected error during /auth/me call.")
             st.session_state.li_connected = False; st.session_state.li_token_data = None; st.session_state.li_user_info = None
             st.session_state.auth_error = f"Error inesperado sesión: {e}"; verified = False
    else: 
        logger.debug("No existing LinkedIn token found in session state to verify.") 
        verified = False

    st.session_state.session_verified = True
    logger.debug(f"verify_session_on_load finished. Verified status: {verified}, li_connected: {st.session_state.get('li_connected')}")
    return verified


def process_auth_params():
    """
    Checks URL query parameters for auth info after OAuth redirect.
    Run AFTER verify_session_on_load. Only processes if no verified session exists.
    Devuelve True si procesó parámetros exitosamente, False en caso contrario.
    """
    # Solo procesar si no tenemos ya una sesión verificada Y no hemos procesado params antes
    if st.session_state.get("session_verified", False) and (st.session_state.get("li_connected")):
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

            if auth_provider == "linkedin":
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
    Loads user's own profile and any managed organizations/pages for the specified platform.
    For LinkedIn, it fetches the user's profile info and then their managed organizations.
    Stores the result as a list of dictionaries in st.session_state.user_accounts[platform].
    Each dictionary has a 'type' key ('profile' or 'organization').
    Returns True if accounts were loaded/refreshed, False otherwise.
    """
    if platform != "LinkedIn":
        logger.warning(f"Account loading only implemented for LinkedIn, requested for {platform}")
        return False

    # Verificar si ya hemos cargado en esta ejecución y no forzamos recarga (evitar llamadas API innecesarias)
    # Puedes añadir un argumento force_reload=False si quieres controlarlo más finamente
    if f"{platform}_accounts_loaded_flag" in st.session_state and st.session_state[f"{platform}_accounts_loaded_flag"]:
        logger.debug(f"Accounts for {platform} already loaded in this session run.")
        return False # Ya estaban cargadas

    is_connected = st.session_state.get("li_connected", False)
    token_dict = st.session_state.get("li_token_data")
    # Usar la información de usuario ya almacenada en session_state
    user_info = st.session_state.get("li_user_info")

    if not is_connected or not token_dict or not isinstance(token_dict, dict) \
       or not user_info or not isinstance(user_info, dict):
        logger.warning("Cannot load accounts for LinkedIn: Not connected, token missing/invalid, or user info missing/invalid.")
        return False

    user_access_token = token_dict.get("access_token")
    # El ID ('sub') del usuario de la información obtenida durante el login/verificación
    user_profile_id = user_info.get("sub")
    user_profile_name = user_info.get("name", "Your Profile")
    user_profile_picture = user_info.get("picture") # Obtener foto de perfil si existe

    if not user_access_token or not user_profile_id:
        logger.error("Cannot load accounts for LinkedIn: Access token or User ID (sub) missing from session state.")
        return False

    logger.info(f"Loading accounts structure for {platform} (Profile + Organizations)...")
    accounts_list = []
    loaded_something_new = False # Flag para saber si hubo cambios

    # --- 1. Añadir el perfil personal del usuario ---
    # Construir el URN de persona
    person_urn = f"urn:li:person:{user_profile_id}"
    profile_account = {
        "id": person_urn, # Usar URN como ID consistente
        "urn": person_urn,
        "name": user_profile_name, # Nombre del usuario
        "platform": "LinkedIn",
        "type": "profile", # <<< Tipo 'profile' para distinguir
        "logo": {"picture": user_profile_picture} # Usar 'logo' para consistencia, poner foto aquí
    }
    accounts_list.append(profile_account)
    logger.debug(f"Added personal profile to account list: {profile_account['name']}")
    # Consideramos esto un cambio inicial si la lista estaba vacía antes
    if not st.session_state.user_accounts.get("LinkedIn"):
        loaded_something_new = True

    # --- 2. Intentar cargar organizaciones administradas ---
    try:
        logger.debug(f"Fetching managed LinkedIn organizations for user {user_profile_id}...")
        # Usamos la función API que ya debería devolver la lista formateada
        # con 'urn', 'id', 'name', 'platform', 'logo', y 'type'='organization'
        managed_organizations = get_linkedin_organizations(user_access_token)

        if isinstance(managed_organizations, list):
            logger.info(f"Received {len(managed_organizations)} managed LI organizations from API.")
            # Filtrar Nones o errores si la API pudiera devolverlos
            valid_orgs = [org for org in managed_organizations if isinstance(org, dict) and org.get('type') == 'organization']

            # Comparar con lo que ya teníamos para ver si hubo cambios
            current_orgs_urns = {acc.get('urn') for acc in st.session_state.user_accounts.get("LinkedIn", []) if acc.get('type') == 'organization'}
            new_orgs_urns = {org.get('urn') for org in valid_orgs}

            if current_orgs_urns != new_orgs_urns:
                loaded_something_new = True
                logger.debug("Organization list changed.")

            accounts_list.extend(valid_orgs) # Añadir organizaciones válidas a la lista

        elif managed_organizations is None:
            logger.warning("get_linkedin_organizations returned None. Assuming no managed organizations.")
            # Verificar si antes sí había organizaciones para marcar cambio
            if any(acc.get('type') == 'organization' for acc in st.session_state.user_accounts.get("LinkedIn", [])):
                loaded_something_new = True
        else:
             logger.error(f"get_linkedin_organizations returned unexpected type: {type(managed_organizations)}")
             # Marcar cambio si antes había organizaciones
             if any(acc.get('type') == 'organization' for acc in st.session_state.user_accounts.get("LinkedIn", [])):
                loaded_something_new = True


    except Exception as e:
        logger.exception(f"Failed loading LinkedIn organizations due to exception: {e}")
        st.error(f"Error cargando organizaciones de LinkedIn: {e}")
        # No fallar, continuar solo con el perfil si ya se añadió
        # Marcar cambio si antes había organizaciones y ahora no
        if any(acc.get('type') == 'organization' for acc in st.session_state.user_accounts.get("LinkedIn", [])):
            loaded_something_new = True


    # --- 3. Actualizar st.session_state si hubo cambios ---
    if loaded_something_new:
        logger.info(f"Updating session state with {len(accounts_list)} total accounts for {platform}.")
        if not isinstance(st.session_state.user_accounts, dict):
            st.session_state.user_accounts = {} # Asegurar que es un dict
        st.session_state.user_accounts[platform] = accounts_list

        # Resetear selección si la lista cambió para forzar re-selección o default
        # Opcional: intentar mantener la selección si el URN todavía existe
        current_selection = st.session_state.get("selected_account")
        if current_selection:
             current_urn = current_selection.get("urn")
             if current_urn not in {acc.get("urn") for acc in accounts_list}:
                  logger.info("Previously selected account no longer available. Resetting selection.")
                  st.session_state.selected_account = None
             else:
                  logger.debug("Previously selected account still available.")
        else:
             st.session_state.selected_account = None # Asegurar None si no había nada

        # Seleccionar el perfil personal por defecto si no hay nada seleccionado después del reset/cambio
        if st.session_state.get("selected_account") is None and accounts_list:
             st.session_state.selected_account = accounts_list[0] # Seleccionar el perfil personal (índice 0)
             logger.info(f"Default account selected after load/refresh: {accounts_list[0].get('name')}")

    else:
        logger.debug(f"No changes detected in account list for {platform}.")

    # Marcar que la carga se intentó/realizó en esta ejecución
    st.session_state[f"{platform}_accounts_loaded_flag"] = True

    # Devolver True si hubo cambios o si la carga fue exitosa (incluso si no hubo cambios)
    # O devolver `loaded_something_new` si solo quieres indicar si hubo cambios.
    # Devolver True indica que la carga se completó (con o sin cambios).
    return True # Indica que el proceso de carga se completó

def display_auth_status(sidebar: bool = True):
    """Display auth status, user info, and disconnect button below profile info."""
    container = st.sidebar if sidebar else st

    # --- Sección Superior: Información del Usuario y Disconnect ---
    if st.session_state.get("li_connected"):
        user_info = st.session_state.get("li_user_info")
        profile_pic_url = None
        display_name = "LinkedIn User"
        logger.debug(f"Session State from display_auth_status: {st.session_state}")

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
    """
    Displays a selector for LinkedIn Profile/Organizations using plain text options.
    """
    container = st.sidebar if sidebar else st

    if not st.session_state.get("li_connected"):
        container.info("Connect to LinkedIn to select an account.")
        if st.session_state.get("selected_account") is not None:
            st.session_state.selected_account = None
        return None

    user_accounts_dict = st.session_state.get("user_accounts", {})
    linkedin_accounts = []
    if isinstance(user_accounts_dict, dict):
        accounts_from_state = user_accounts_dict.get("LinkedIn", [])
        if isinstance(accounts_from_state, list):
            linkedin_accounts = accounts_from_state
        else: logger.warning("LinkedIn accounts data in session state is not a list.")
    else: logger.warning("user_accounts in session state is not a dictionary.")

    if not linkedin_accounts:
        container.warning("No LinkedIn profile or organizations found/loaded.")
        if st.session_state.get("selected_account") is not None:
            st.session_state.selected_account = None
        return None

    container.subheader("🎯 Active Account")

    # --- Caso: Solo el perfil personal ---
    if len(linkedin_accounts) == 1 and linkedin_accounts[0].get("type") == "profile":
        profile_info = linkedin_accounts[0]
        # Solo mostrar texto aquí también para consistencia
        container.info(f"Using: **{profile_info.get('name', 'Your Profile')}** (Profile)")
        if st.session_state.get("selected_account") != profile_info:
             st.session_state.selected_account = profile_info
        return st.session_state.selected_account

    # --- Caso: Múltiples cuentas (perfil + organizaciones) ---
    else:
        def format_account_option_text(account_dict):
            if account_dict is None:
                return "Select Account..." # Placeholder si usamos None
            name = account_dict.get('name', 'Unknown Account')
            acc_type = account_dict.get('type', 'unknown').capitalize()
            # Quitar información extra del nombre del perfil si existe
            if acc_type == 'Profile':
                name = name.replace(" (Personal Profile)", "")
            return f"{name} ({acc_type})"

        currently_selected_account = st.session_state.get("selected_account")
        current_index = 0
        options_list = linkedin_accounts

        if isinstance(currently_selected_account, dict):
            current_urn = currently_selected_account.get('urn')
            if current_urn:
                try:
                    current_index = next(i for i, acc in enumerate(options_list)
                                         if isinstance(acc, dict) and acc.get('urn') == current_urn)
                except StopIteration:
                    logger.warning(f"Previously selected account URN {current_urn} not found. Defaulting.")
                    current_index = 0
                    st.session_state.selected_account = options_list[0] if options_list else None
            else:
                 current_index = 0
                 st.session_state.selected_account = options_list[0] if options_list else None
        elif options_list:
             current_index = 0
             st.session_state.selected_account = options_list[0]

        # --- Usar st.selectbox (más compacto) o st.radio con format_func de texto ---
        # Volvemos a selectbox ya que no necesitamos renderizar HTML
        selected_index = container.selectbox(
            label="Select Profile or Organization",
            options=range(len(options_list)), # Opciones son los índices
            format_func=lambda i: format_account_option_text(options_list[i]), # << USA LA VERSIÓN DE TEXTO
            index=current_index,
            key="linkedin_account_selector", # Reusar clave o cambiar si da problemas
            help="Choose your personal profile or an organization page to interact with."
        )
        # --- FIN WIDGET ---

        newly_selected_account = options_list[selected_index]

        # Actualizar el estado y Rerun SI la selección cambió
        previous_urn = st.session_state.get("selected_account", {}).get('urn') if isinstance(st.session_state.get("selected_account"), dict) else None
        new_urn = newly_selected_account.get('urn')

        if new_urn != previous_urn:
            st.session_state.selected_account = newly_selected_account
            if newly_selected_account:
                logger.info(f"Account selection changed to: {format_account_option_text(newly_selected_account)}")
            else:
                logger.error(f"Newly selected account is invalid (Index: {selected_index})") # Log si algo va mal
            st.rerun()

        return st.session_state.get("selected_account")
