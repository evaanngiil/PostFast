import streamlit as st
import requests
import json
import base64
from datetime import datetime, timezone
from typing import Optional
import requests.sessions
from urllib.parse import unquote_plus
from src.services.supabase_client import get_supabase
from src.supabase_auth import (
    revalidate_aipost_session,
    mark_aipost_logged_in,
    is_aipost_logged_in,
)

try:
    from src.core.constants import FASTAPI_URL
except ImportError:
    FASTAPI_URL = "http://localhost:8000"

try:
    from src.core.logger import logger
except ImportError:
    import logging; logger = logging.getLogger(__name__); logger.warning("Using basic logger.")

try:
    from fastapi import Depends, HTTPException
    from fastapi.security import OAuth2PasswordBearer
except Exception:
    def Depends(x=None): return x
    class HTTPException(Exception): pass
    class OAuth2PasswordBearer: pass
try:
    from streamlit.components.v1 import html as components_html
except Exception:
    def components_html(content, height=0): pass

try:
    from src.social_apis import get_linkedin_organizations, get_linkedin_user_info
except ImportError:
    logger.error("Dummy social API funcs used.")
    def get_linkedin_organizations(token): return []
    def get_linkedin_user_info(token): return {'sub': 'dummy_user_sub', 'name': 'Dummy User', 'email': 'dummy@example.com'}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


# ----------------- INICIALIZADORES / HELPERS -----------------

def get_current_session_data_from_token(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        supabase = get_supabase()
        resp = supabase.table("user_sessions").select("*").eq("access_token", token).single().execute()
        result = resp.data
        if not result:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        expires_at_db = result.get('expires_at')
        token_expired = False
        if expires_at_db:
            expires_at_aware = datetime.fromisoformat(expires_at_db.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_at_aware:
                token_expired = True
        
        if token_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        user_info_out = result.get('user_info') if isinstance(result.get('user_info'), dict) else {}

        return {
            "authenticated": True, "provider": result.get('provider'), "user_info": user_info_out,
            "user_provider_id": result.get('user_provider_id'),
            "session_cookie_id": result.get('session_cookie_id'),
            "token_data": {
                "access_token": result.get('access_token'), "refresh_token": result.get('refresh_token'),
                "token_type": result.get('token_type'), "expires_at": expires_at_db
            }
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"[Dependency] Unexpected error verifying token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _validate_platform_session():
    return is_aipost_logged_in()

def ensure_session_initialized(force=False):
    """Inicializa y valida la sesión en el orden correcto."""
    # La inicialización debe ocurrir en cada página, no aquí.
    if not st.session_state.get('session_revalidated', False) or force:
        revalidate_aipost_session()

    # process_auth_params se encargará de hacer switch_page si tiene éxito
    if not process_auth_params():
        # Si no se procesaron parámetros, intentar verificar una sesión existente
        verify_session_on_load()

    if st.session_state.get('li_connected') and not st.session_state.get('LinkedIn_accounts_loaded_flag'):
        load_user_accounts('LinkedIn')
    return True

def initialize_session_state():
    """Debe ser llamada al principio de cada script de página."""
    defaults = {
        'aipost_logged_in': False, 'user': None, 'session_revalidated': False,
        'li_connected': False, 'li_user_info': None, 'li_token_data': None,
        'user_accounts': {}, 'LinkedIn_accounts_loaded_flag': False,
        'session_verified': False, 'auth_error': None, 'selected_account': None
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v


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
    Procesa los parámetros de la URL. Devuelve True si se procesó algo.
    Se encarga de limpiar la URL y hacer switch_page en caso de éxito.
    """
    query_params = st.query_params
    logger.debug(f"[process_auth_params] raw query_params: {dict(query_params)}")

    auth_provider = query_params.get("auth_provider")
    auth_error = query_params.get("auth_error")

    if not auth_provider and not auth_error:
        return False

    if auth_error:
        st.session_state.auth_error = f"Error de autenticación: {auth_error}"
        try: 
            st.query_params.clear()
        except Exception: 
            pass
        return True

    auth_token_encoded = query_params.get("auth_token")
    user_info_b64 = query_params.get("user_info")
    create_platform_session = query_params.get("create_platform_session")

    logger.debug(f"[process_auth_params] provider={auth_provider} token_present={bool(auth_token_encoded)} create_platform_session={create_platform_session}")

    if auth_provider and auth_token_encoded:
        try:
            access_token = unquote_plus(auth_token_encoded)
            token_data = {"access_token": access_token}

            st.session_state.li_token_data = token_data
            logger.info("[process_auth_params] Stored li_token_data into session_state")

            user_info = {}
            if user_info_b64:
                logger.debug(f"[process_auth_params] user_info_b64 preview: {str(user_info_b64)[:120]} (len={len(user_info_b64)})")
                
                def _decode_b64_str(s: str):
                    if isinstance(s, str): 
                        s_bytes = s.encode()
                    else: 
                        s_bytes = s
                        
                    padding = b"=" * (-len(s_bytes) % 4)
                    try: 
                        return base64.urlsafe_b64decode(s_bytes + padding).decode()
                    except Exception: 
                        return base64.b64decode(s_bytes + padding).decode()

                try:
                    s = user_info_b64
                    if isinstance(s, str) and (s.lstrip().startswith('{') or s.lstrip().startswith('[') or s.startswith('%7B')):
                        try: 
                            user_info = json.loads(unquote_plus(s))
                        except Exception: 
                            user_info = json.loads(s)
                    else:
                        try:
                            user_info = json.loads(_decode_b64_str(s))
                        except Exception:
                            try: 
                                user_info = json.loads(_decode_b64_str(unquote_plus(s)))
                            except Exception:
                                logger.exception("[process_auth_params] Failed decoding user_info; continuing with empty user_info")
                                user_info = {}
                except Exception:
                    logger.exception("[process_auth_params] Unexpected error while parsing user_info")
                    user_info = {}

            st.session_state.li_user_info = user_info
            logger.info("[process_auth_params] Stored li_user_info into session_state")

            if auth_provider == "linkedin":
                if create_platform_session == "true":
                    email = user_info.get('email')
                    name = user_info.get('name', 'Usuario LinkedIn')
                    if email:
                        mock_user = type('MockUser', (), {'email': email, 'name': name, 'user_metadata': {'name': name, 'email': email}})()
                        mark_aipost_logged_in(mock_user)
                    else:
                        st.session_state.auth_error = "No se pudo obtener el email de LinkedIn."
                        try: 
                            st.query_params.clear()
                        except Exception: 
                            pass
                        return True
                elif not is_aipost_logged_in():
                    st.session_state.auth_error = "Debes iniciar sesión en AIPost primero."
                    try: 
                        st.query_params.clear()
                    except Exception: 
                        pass
                    return True

                # --- marcar conectado antes de cambiar de página ---
                st.session_state.li_connected = True
                st.session_state.session_verified = True
                logger.info("LinkedIn session established in session_state. Switching to Dashboard.")

                try: 
                    st.query_params.clear()
                except Exception: 
                    pass
                
                try: 
                    st.switch_page("pages/01_Dashboard.py")
                except Exception: 
                    st.rerun()

        except Exception:
            logger.exception("Error processing auth params from URL.")
            st.session_state.auth_error = "Error procesando datos de autenticación."
            try: st.query_params.clear()
            except Exception: pass
            return True

    return True


def load_user_accounts(platform: str) -> bool:
    if platform != "LinkedIn" or st.session_state.get(f"{platform}_accounts_loaded_flag"):
        return False

    is_connected = st.session_state.get("li_connected", False)
    token_dict = st.session_state.get("li_token_data")
    user_info = st.session_state.get("li_user_info")

    if not (is_connected and token_dict and user_info):
        return False

    user_access_token = token_dict.get("access_token")
    user_profile_id = user_info.get("sub")
    if not user_access_token or not user_profile_id:
        return False

    logger.info(f"Loading accounts for {platform}...")
    accounts_list = []
    person_urn = f"urn:li:person:{user_profile_id}"
    accounts_list.append({
        "id": person_urn, "urn": person_urn, "name": user_info.get("name", "Your Profile"),
        "platform": "LinkedIn", "type": "profile", "logo": {"picture": user_info.get("picture")}
    })

    try:
        managed_organizations = get_linkedin_organizations(user_access_token)
        if isinstance(managed_organizations, list):
            accounts_list.extend(managed_organizations)
    except Exception as e:
        logger.exception(f"Failed loading LinkedIn organizations: {e}")
        st.error(f"Error cargando organizaciones de LinkedIn: {e}")

    st.session_state.user_accounts[platform] = accounts_list
    if st.session_state.get("selected_account") is None and accounts_list:
        st.session_state.selected_account = accounts_list[0]
    
    st.session_state[f"{platform}_accounts_loaded_flag"] = True
    return True

def display_auth_status(sidebar: bool = True):
    container = st.sidebar if sidebar else st
    if not is_aipost_logged_in():
        container.info("Inicia sesión en AIPost para conectar redes sociales.")
        return

    logger.warning(f"[auth-status] Displaying auth status... {st.session_state}")
    if st.session_state.get("li_connected"):
        user_info = st.session_state.get("li_user_info")
        display_name, profile_pic_url = "Usuario LinkedIn", None
        if isinstance(user_info, dict):
            display_name = user_info.get('name', display_name)
            profile_pic_url = user_info.get('picture')
        
        col_img, col_info = container.columns([1, 4])
        with col_img:
            if profile_pic_url: st.image(profile_pic_url, width=45)
            else: st.markdown("👤", unsafe_allow_html=True)
        with col_info:
            st.markdown(f"**{display_name}**")
            st.caption("Conectado a LinkedIn")

        if container.button("Desconectar LinkedIn", key="disconnect_li_btn", use_container_width=True):
            st.session_state.li_connected = False
            st.session_state.li_token_data = None
            st.session_state.li_user_info = None
            if isinstance(st.session_state.get("user_accounts"), dict):
                st.session_state.user_accounts.pop("LinkedIn", None)
            st.session_state.selected_account = None
            try: 
                requests.get(f"{FASTAPI_URL}/auth/logout", timeout=5)
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

    linkedin_accounts = (st.session_state.get("user_accounts") or {}).get("LinkedIn", [])
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