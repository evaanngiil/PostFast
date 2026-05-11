import streamlit as st
import os
import requests
import json
import base64
from urllib.parse import unquote_plus
from streamlit_cookies_controller import CookieController

from src.supabase_auth import (
    revalidate_aipost_session,
    mark_aipost_logged_in,
    is_aipost_logged_in,
    get_or_create_linkedin_profile,
    sync_linkedin_orgs_to_db,
    get_user_profile,
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

try:
    from src.services.api_client import (
        is_first_company_connection,
    )
    from src.tasks import company_batch_extraction_task, company_batch_refresh_task
except ImportError:
    logger.warning("company_batch imports not available -- batch extraction disabled.")
    def is_first_company_connection(org_urn): return False
    company_batch_extraction_task = None
    company_batch_refresh_task = None


def _trigger_company_batch_if_first_connect(orgs: list, access_token: str) -> None:
    """
    Desencadena tareas batch de Celery para enriquecer perfiles de organizaciones.

    :param orgs: Lista de organizaciones de LinkedIn asociadas al usuario.
    :param access_token: Token de acceso de la sesión de LinkedIn.
    :returns: None
    """
    if not orgs:
        return

    for org in orgs:
        org_urn  = org.get("urn")
        org_name = org.get("name", "Empresa Desconocida")

        if not org_urn:
            logger.warning(f"Organizacion sin URN, omitiendo batch: {org}")
            continue

        try:
            if is_first_company_connection(org_urn):
                if not company_batch_extraction_task:
                    logger.warning("company_batch_extraction_task no disponible; extraccion omitida.")
                    continue
                logger.info(
                    f"[batch] Primera conexion para '{org_name}' ({org_urn}). "
                    "Encolando extraccion completa..."
                )
                company_batch_extraction_task.delay(
                    org_urn=org_urn,
                    org_name=org_name,
                    access_token=access_token,
                )
                logger.info(f"[batch] company_batch_extraction_task encolada para {org_urn}")
            else:
                if not company_batch_refresh_task:
                    logger.warning("company_batch_refresh_task no disponible; chequeo omitido.")
                    continue

                # Encolar directamente — Celery gestiona la deteccion de cambios
                logger.info(
                    f"[batch] Perfil existente para '{org_name}' ({org_urn}). "
                    "Encolando refresh (Celery hara el probe)..."
                )
                company_batch_refresh_task.delay(
                    org_urn=org_urn,
                    org_name=org_name,
                    access_token=access_token,
                )
                logger.info(f"[batch] company_batch_refresh_task encolada para {org_urn}")

        except Exception as e:
            logger.error(
                f"[batch] Error al encolar tarea para {org_urn}: {e}",
                exc_info=True,
            )



# Caché in-memory a nivel de módulo (aislado de session_state para trackear re-runs).
_cookie_cache: dict = {"instance": None, "run_id": None}


def _get_script_run_id() -> str:
    """
    Extrae el identificador único del ciclo de ejecución actual de Streamlit.

    :returns: String con el ID del run, o un fallback constante si no hay contexto.
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx:
            return ctx.script_run_id
    except Exception:
        pass
    # Estrategia de fallback para contextos no gestionados por Streamlit (ej. unittests).
    return "__fallback__"


def get_cookie_controller():
    """
    Inicializa o recupera el singleton de gestión de cookies vinculado al ciclo actual.

    :returns: Instancia activa de CookieController.
    """
    current_run_id = _get_script_run_id()

    if _cookie_cache["run_id"] != current_run_id:
        # Iniciar instancia virgen en nuevo ciclo de ejecución.
        _cookie_cache["instance"] = CookieController(key=SECRET_KEY)
        _cookie_cache["run_id"] = current_run_id

    return _cookie_cache["instance"]

# Core Handlers e Inicializadores de Estado.

def initialize_session_state():
    """
    Carga y define el estado inicial in-memory (session_state) requerido por la app.

    :returns: None
    """
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
    """
    Asegura de forma síncrona el flujo correcto de validación de estado y sesión.

    :param force: Booleano para saltar la caché y revalidar forzosamente contra base de datos.
    :returns: True cuando la ejecución finaliza.
    """
    # Control de ejecución centralizado por vista.
    if not st.session_state.get('session_revalidated', False) or force:
        revalidate_aipost_session()

    if not process_auth_params():
        # Recuperación silenciosa si la ruta no tiene payload.
        verify_session_on_load()

    if st.session_state.get('li_connected') and not st.session_state.get('LinkedIn_accounts_loaded_flag'):
        load_user_accounts()
    return True


def verify_session_on_load() -> bool:
    """
    Intenta recuperar proactivamente una sesión desde el backend a través del endpoint `/auth/me`.

    :returns: True si la sesión fue recuperada o ya existía, False en caso contrario.
    """
    if st.session_state.get("li_connected"):
        return True

    logger.debug("Attempting to verify existing session via /auth/me...")
    auth_status_url = f"{FASTAPI_URL}/auth/me"
    headers = {'Accept': 'application/json'}

    try:
        # 1) Preferir token guardado en session_state
        li_token_data = st.session_state.get("li_token_data") or {}
        token = li_token_data.get("access_token") if isinstance(li_token_data, dict) else None

        # 2) FALLBACK: si no hay token en session_state, comprobar query params (util justo despues de la redireccion)
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

        resp = requests.get(auth_status_url, headers=headers, timeout=3)
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
    Lógica de enrutamiento y procesamiento post OAuth callback.

    :returns: True si había payload en URL y fue procesado, False si estaba vacío.
    """
    query_params = st.query_params
    auth_provider = query_params.get("auth_provider")

    if not auth_provider:
        return False # No hay nada que procesar

    logger.debug(f"Processing auth params from URL for provider: {auth_provider}")
    
    # Decodificación de payload.
    auth_token_encoded = query_params.get("auth_token")
    user_info_b64 = query_params.get("user_info")
    create_platform_session = query_params.get("create_platform_session")
    auth_error = query_params.get("auth_error")

    # Reseteo del vector URL params para prevenir loops de rendering en React.
    try:
        st.query_params.clear()
    except Exception:
        pass
    
    # Resolución de abortos y errores inyectados por el router backend.
    if auth_error:
        st.session_state.auth_error = f"Error de autenticacion: {auth_error}"
        st.rerun()
        return True

    # Orquestación de login tras confirmación de provider y existencia de tokens.
    if auth_provider == "linkedin" and auth_token_encoded:
        try:
            # Guardado en memoria y resolución de base64.
            access_token = unquote_plus(auth_token_encoded)
            st.session_state.li_token_data = {"access_token": access_token}
            # Sincronización del auth_token con la vista.
            st.session_state.auth_token_for_url = access_token
            
            user_info_json = base64.urlsafe_b64decode(user_info_b64.encode() + b'==').decode()
            user_info = json.loads(user_info_json)
            
            logger.debug(f"Decoded LinkedIn user info: {user_info}")
            st.session_state.li_user_info = user_info
            
            # Inyección forzosa de estado local.
            st.session_state.li_connected = True
            st.session_state.session_verified = True
            logger.info("LinkedIn session established from URL params.")

            # Dispatch de sesión a nivel de aplicación core (AIPost framework).
            if create_platform_session == "true":
                email = user_info.get('email')
                name = user_info.get('name', 'Usuario LinkedIn')
                provider_id = user_info.get('id') or user_info.get('sub')

                # Estrategia de Account Linking: Fusionar proveedor LinkedIn si el usuario ya existe.
                existing_user = st.session_state.get('user')
                if existing_user and getattr(existing_user, 'id', None):

                    existing_uuid = str(existing_user.id)
                    logger.info(
                        f"[process_auth_params] User {existing_uuid} already "
                        f"logged in. Linking LinkedIn provider {provider_id} "
                        f"to existing profile (no new user created)."
                    )

                    if provider_id:
                        try:
                            from src.services.supabase_client import get_supabase_admin
                            sb = get_supabase_admin()
                            sb.table("user_profiles").update(
                                {"linkedin_provider_id": provider_id}
                            ).eq("id", existing_uuid).execute()
                            get_user_profile.clear()
                            logger.info(
                                f"[process_auth_params] linkedin_provider_id "
                                f"linked to existing profile {existing_uuid}"
                            )
                        except Exception as link_err:
                            logger.warning(
                                f"[process_auth_params] Failed to link "
                                f"linkedin_provider_id: {link_err}"
                            )

                elif email and provider_id:
                    profile = get_or_create_linkedin_profile(provider_id, user_info)
                    profile_uuid = profile['id'] if profile else provider_id

                    mock_user = type('MockUser', (), {
                        'id': profile_uuid,
                        'email': email,
                        'name': name,
                        'user_metadata': {'name': name, 'email': email}
                    })()
                    mark_aipost_logged_in(mock_user)
                    logger.info(f"AIPost platform session created/validated for {email} (UUID: {profile_uuid})")

                # Fallbacks de validación para payloads OAuth incompletos.
                elif not provider_id:
                     st.session_state.auth_error = "No se pudo obtener el ID de usuario de LinkedIn para iniciar sesion."
                     st.session_state.li_connected = False # Revert connection if essential info missing

                elif not email:
                    st.session_state.auth_error = "No se pudo obtener el email de LinkedIn para iniciar sesion."

            # Enrutamiento final post-auth.
            st.switch_page("pages/Dashboard.py")
            
        except Exception as e:
            st.session_state.auth_error = "Error procesando datos de autenticacion."
            logger.exception(f"Failed to process auth params: {e}")
            st.rerun() # Hacemos rerun para mostrar el error

    return True # Indicamos que se procesaron parametros

# Funciones de Soporte y Core Lógico.

def load_user_accounts():
    """
    Recupera el listado de páginas/perfiles que el usuario administra en LinkedIn.

    :returns: None
    """
    
    if st.session_state.get('LinkedIn_accounts_loaded_flag') or not st.session_state.get("li_connected"):
        return

    # Fallback proactivo: Recuperación del token desde data de sesión en caso de omisión.
    token = st.session_state.get('auth_token_for_url')
    if not token:
        li_token_data = st.session_state.get('li_token_data')
        if isinstance(li_token_data, dict):
            token = li_token_data.get('access_token')
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

    managed_orgs = get_linkedin_organizations(token)
    if managed_orgs:
        accounts_list.extend(managed_orgs)

    st.session_state.user_accounts = accounts_list
    if not st.session_state.get("selected_account") and accounts_list:
        st.session_state.selected_account = accounts_list[0]

    st.session_state.LinkedIn_accounts_loaded_flag = True
    logger.info(f"Loaded {len(accounts_list)} LinkedIn accounts.")

    # Sincronización proactiva de instancias (Tenants) corporativas de LinkedIn hacia BD.
    # Dispara inserts base para tenants nuevos y propaga la metadata de onboarding base.
    # Operación idempotente garantizada (skipea URNs previamente mapeados).
    user = st.session_state.get("user")
    if managed_orgs and user:
        try:
            sync_linkedin_orgs_to_db(str(user.id), managed_orgs)
        except Exception as e:
            logger.error(f"[load_user_accounts] sync_linkedin_orgs_to_db failed: {e}")

    # Encolamiento reactivo de tareas de scraping per-tenant al registrar la primera conexión.
    # El bloqueo en session_state previene ejecuciones duplicadas generadas por el flujo React/Streamlit.
    if managed_orgs and not st.session_state.get("_company_batch_triggered"):
        st.session_state["_company_batch_triggered"] = True
        _trigger_company_batch_if_first_connect(managed_orgs, token)


def _restore_session_from_api(token: str) -> bool:
    """
    Intenta reconstruir la sesión revalidando el token contra el backend.

    :param token: Access token a validar.
    :returns: True si el token es activo, False si falló.
    """
    if not token: return False
        
    logger.debug("Attempting to restore session from API via /auth/me")
    auth_status_url = f"{FASTAPI_URL}/auth/me"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(auth_status_url, headers=headers, timeout=3)
        if resp.ok:
            auth_data = resp.json()
            if auth_data.get("authenticated"):
                provider = auth_data.get("provider")
                user_info = auth_data.get("user_info", {})
                
                # Poblar estado de la plataforma AIPost
                st.session_state.aipost_logged_in = True
                # Resolución crítica: Mapeo heurístico del UUID subyacente.
                # Para perfiles de LinkedIn el identificador OAuth diverge de los UUIDs
                # del Postgres schema; solicitamos a capa abstracta su resolución y/o binding local.
                provider_id = (
                    auth_data.get('user_provider_id')
                    or user_info.get('id')
                    or user_info.get('sub')
                )
                if provider == "linkedin" and provider_id:
                    # user_sessions.user_info puede carecer de email — se complementa
                    # con li_user_info almacenado en session_state (seteado en el login inicial)
                    li_cached = st.session_state.get('li_user_info') or {}
                    merged_info = {**li_cached, **{k: v for k, v in user_info.items() if v}}

                    # Prevención de race conditions: validar la pre-existencia de binding antes del upsert.
                    profile = None
                    try:
                        from src.services.supabase_client import get_supabase_admin
                        sb = get_supabase_admin()
                        existing = (
                            sb.table("user_profiles")
                            .select("*")
                            .eq("linkedin_provider_id", provider_id)
                            .maybe_single()
                            .execute()
                        )
                        if existing and existing.data:
                            profile = existing.data
                            logger.debug(
                                f"[restore] Found existing profile by "
                                f"linkedin_provider_id={provider_id}: {profile['id']}"
                            )
                    except Exception as e:
                        logger.warning(f"[restore] linkedin_provider_id lookup failed: {e}")

                    if not profile:
                        profile = get_or_create_linkedin_profile(provider_id, merged_info)
                    resolved_id = profile['id'] if profile else provider_id
                else:
                    # Passthrough para bindings estándar de UUID (ej: email/password).
                    # ya es un UUID de Supabase Auth.
                    resolved_id = user_info.get('id') or user_info.get('sub') or provider_id

                # Resolución secundaria del email desde base de datos relacional si OAuth omite el dato.
                resolved_email = (
                    user_info.get('email')
                    or (profile.get('email') if profile else None)
                )
                user_data_for_mock = {
                    'id': resolved_id,
                    'user_metadata': user_info,
                    'email': resolved_email,
                    'name': user_info.get('name'),
                }
                st.session_state.user = type('MockUser', (), user_data_for_mock)()
                
                # Inyección del token activo en la traza de routing.
                st.session_state.auth_token_for_url = token

                if provider == "linkedin":
                    st.session_state.li_user_info = user_info
                    st.session_state.li_connected = True
                
                st.session_state.session_verified = True
                logger.info(f"Session restored from API for provider: {provider}")
                return True
        else:
            logger.warning(f"API rejected token. Status: {resp.status_code}")
            st.session_state.auth_error = "Tu sesion ha expirado o es invalida."
            
    except Exception as e:
        logger.error(f"Error during API session restoration: {e}")
        st.session_state.auth_error = "Error de conexion al verificar la sesion."

    # Estrategia de degradación suave (graceful degradation) para fallos del OAuth token.
    # Si la sesión maestra de base de datos sigue activa, preservamos el logged-in state.
    has_valid_supabase_session = (
        st.session_state.get('user') is not None
        and st.session_state.get('aipost_logged_in')
    )
    st.session_state.li_connected = False
    st.session_state.auth_token_for_url = None
    if not has_valid_supabase_session:
        st.session_state.aipost_logged_in = False
    else:
        logger.info(
            "[restore] LinkedIn token rejected but valid Supabase session exists. "
            "Preserving aipost_logged_in."
        )
        # Limpiar el auth_error estancado ya que el usuario ESTA autenticado
        st.session_state.auth_error = None
    return False


def _reinforce_cookie(cookies, token: str) -> None:
    """
    Refuerza la integridad de la cookie activa interactuando con el iframe proxy de React.

    :param cookies: Referencia al controlador de cookies en memoria.
    :param token: JWT que será guardado.
    :returns: None
    """
    if not token:
        return
    try:
        cookies.set("linkedin_access_token", token, max_age=7 * 24 * 60 * 60)  # 7 dias
    except Exception as e:
        logger.warning(f"No se pudo establecer/reforzar la cookie: {e}")


def ensure_auth(protect_route: bool = True):
    """
    Middleware principal de ruteo. Verifica el estado y restringe el acceso a rutas protegidas.

    :param protect_route: Booleano para forzar redirect al login si no está autorizado.
    :returns: None
    """
    initialize_session_state()
    cookies = get_cookie_controller()

    # Fase 1: Bypass temprano si la autorización ya se constató en memoria.
    #    - Reforzar la cookie (puede no haberse persistido en el run anterior)
    #    - Luego salir.
    if st.session_state.get('session_verified'):
        # Reforzamiento asíncrono preventivo: asegura consolidación del cookie layer en React.
        token = st.session_state.get('auth_token_for_url')
        if not token:
            td = st.session_state.get('li_token_data')
            if isinstance(td, dict):
                token = td.get('access_token')
        _reinforce_cookie(cookies, token)
        load_user_accounts()
        return

    # Fase 2: Ping al backend de base de datos para revalidación maestra local.
    revalidate_aipost_session()

    # Fase 3: Scanning de tokens embebidos (URL params o sesión reactiva).
    token = st.query_params.get("auth_token") or st.session_state.get('auth_token_for_url')
    logger.debug(f"[ensure_auth] auth_token from URL or session_state: {'PRESENT' if token else 'NOT PRESENT'}")

    if token is not None:
        _reinforce_cookie(cookies, token)
    else:
        # Intento de bypass fallback leyendo directamente el state del iframe (CookieController).
        # Debido al lifecycle asíncrono de React, este read puede ser inestable en primeros renders.
        token = cookies.get("linkedin_access_token")

        if token:
            st.session_state.li_token_data = {"access_token": token}
            st.session_state.auth_token_for_url = token
            logger.debug("[ensure_auth] auth_token recovered from cookies and stored in session_state")
        elif not st.session_state.get("_cookie_retry_done") and protect_route:
            # Workaround React DOM: Inyección de un rerun controlado para darle tiempo al iframe
            # iframe-controller para mount y fetch del JWT pasivo.
            st.session_state["_cookie_retry_done"] = True
            logger.debug("[ensure_auth] cookie returned None on protected route; scheduling one retry for React iframe")
            st.rerun()
    
    if token:
        logger.debug(f"[ensure_auth] TOKEN present, restoring session via API...")
        if _restore_session_from_api(token):
            # Purga de inyección vía params en URL para enrutamiento limpio.
            if "auth_token" in st.query_params:
                st.query_params.clear()
            # Terminación de middleware con éxito e inyección de contexto de tenants corporativos.
            load_user_accounts()
            return

    # Control de Gatekeeper de Rutas Protegidas: Bloqueo explícito tras agotar flujos de restauración.
    # Posicionado estratégicamente para dar al iframe oportunidad de carga.
    if protect_route and not st.session_state.get('aipost_logged_in'):
        st.warning("Debes iniciar sesion para acceder a esta pagina.")
        st.switch_page("app.py")
        st.stop()

    # Fase 4: Manejo de handshakes remotos generados vía redirección explícita post-OAuth backend.
    if "auth_provider" in st.query_params and st.query_params.get("auth_provider") == "linkedin":
        token_from_url = st.query_params.get("auth_token")
        if token_from_url:
            st.session_state.auth_token_for_url = token_from_url
            st.query_params.clear() # Prevención bucle de inyección
            # Force triggering del árbol de re-renderizado para absorber payload remoto.
            st.rerun()



# Módulos Visuales Auxiliares (UI Elements).
def display_auth_status(sidebar: bool = True):
    # Pre-warm del controller de cookies necesario para inyectar handlers en el botón.
    cookies = get_cookie_controller()
    container = st.sidebar if sidebar else st
    if not is_aipost_logged_in():
        container.info("Inicia sesion en AIPost para conectar redes sociales.")
        return

    logger.warning(f"[auth-status] Displaying auth status UI Sidebar{st.session_state}")

    if st.session_state.get("li_connected"):
        logger.debug("HAY CONEXION A LINKEDIN - mostrando estado en sidebar")
        
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
                st.markdown("<span style='font-size:2em'>&#128100;</span>", unsafe_allow_html=True)
                
        with col_info:
            st.markdown(f"**{display_name}**")
            st.caption("Conectado a LinkedIn")

        if container.button("Desconectar LinkedIn", key="disconnect_li_btn", use_container_width=True):
            cookies.remove("linkedin_access_token")

            st.session_state.li_connected = False
            st.session_state.li_token_data = None
            st.session_state.li_user_info = None
            st.session_state.user_accounts = []
            st.session_state.selected_account = None
            # Purgado y flush total del state local para forzar refetch en próxima carga.
            st.session_state.pop("_company_batch_triggered", None)
            st.session_state.pop("LinkedIn_accounts_loaded_flag", None)
            st.session_state.pop("session_verified", None)
            st.session_state.pop("auth_token_for_url", None)
            st.session_state.pop("_cookie_retry_done", None)
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
        
        container.link_button("Conectar LinkedIn", f"{FASTAPI_URL}/auth/login/linkedin", use_container_width=True)

def display_account_selector(sidebar: bool = True):
    container = st.sidebar if sidebar else st
    if not st.session_state.get("li_connected"):
        return None

    linkedin_accounts = (st.session_state.get("user_accounts") or {})
    if not linkedin_accounts:
        container.warning("No se encontraron perfiles de LinkedIn.")
        return None

    container.subheader("Cuenta Activa")
    
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
            "Selecciona un Perfil u Organizacion",
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
