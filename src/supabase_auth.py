import streamlit as st
from supabase import AuthApiError
from src.services.supabase_client import get_supabase
from typing import Optional
from src.core.logger import logger

supabase = get_supabase()

# --- FUNCIONES DE AUTENTICACIÓN (AIPost) ---
def get_current_user() -> Optional[object]:
    """Devuelve el usuario actual de Supabase o None si no hay sesión activa."""
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            return session.user
        return None
    except Exception as e:
        st.error(f"Error al obtener el usuario actual: {e}")
        return None


def signup(email: str, password: str) -> bool:
    """Registra un nuevo usuario en Supabase. No realiza login automático."""
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})

        if getattr(res, "user", None):
            st.success("¡Registro exitoso! Revisa tu email para verificar tu cuenta.")
            return False  # No se loguea hasta verificar
        return False
    except AuthApiError as e:
        st.error(f"Error en el registro: {e.message}")
        return False
    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
        return False


# -- funciones de responsabilidad única para estado AIPost --
def mark_aipost_logged_in(user: object) -> None:
    """Marca al usuario como logueado en AIPost y guarda el objeto user."""
    st.session_state['aipost_logged_in'] = True
    st.session_state['user'] = user


def mark_aipost_logged_out() -> None:
    """Marca al usuario como no logueado en AIPost y limpia la info de usuario."""
    st.session_state['aipost_logged_in'] = False
    st.session_state['user'] = None


def is_aipost_logged_in() -> bool:
    """Comprueba si hay un usuario logueado en AIPost."""
    return bool(st.session_state.get('aipost_logged_in'))


def get_aipost_user() -> Optional[object]:
    """Devuelve el objeto user almacenado para AIPost o None."""
    return st.session_state.get('user')


def login(email: str, password: str) -> bool:
    """Inicia sesión de un usuario existente en Supabase y marca AIPost como logueado."""
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        mark_aipost_logged_in(res.user)
        return True
    except AuthApiError as e:
        st.error(f"Error en el inicio de sesión: {e.message}")
        return False
    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
        return False


def logout() -> None:
    """Cierra sesión limpiando session_state y cookies (solo AIPost-related keys aquí)."""
    try:
        supabase.auth.sign_out()
    except Exception as e:
        logger.error(f"Error signing out: {e}")

    # Limpiar específicamente las claves de LinkedIn (no tocar aquí la semántica de LinkedIn)
    linkedin_keys_to_delete = [
        'li_connected', 'li_token_data', 'li_user_info', 'user_accounts',
        'selected_account', 'auth_error', 'processed_auth_params',
        'session_verified', 'LinkedIn_accounts_loaded_flag'
    ]
    for k in linkedin_keys_to_delete:
        st.session_state.pop(k, None)

    # Limpiar variables específicas de AIPost
    mark_aipost_logged_out()
    st.query_params.clear()

    # Call backend logout to clean up server-side session (best-effort)
    try:
        import requests
        from src.core.constants import FASTAPI_URL
        logout_url = f"{FASTAPI_URL}/auth/logout"
        with requests.sessions.Session() as session:
            response = session.get(logout_url, timeout=10)
            logger.debug(f"Backend logout response: {response.status_code}")
    except Exception as e:
        logger.warning(f"Failed to call backend logout: {e}")

    try:
        st.rerun()
    except Exception:
        st.info("Sesión cerrada. Recarga manualmente para volver al login.")


def revalidate_aipost_session() -> None:
    """
    Comprueba si hay una sesión de Supabase activa y actualiza st.session_state (AIPost-only).
    Debe llamarse al principio de cada script de página protegida.
    """
    # Evita re-validaciones innecesarias en la misma ejecución del script
    if st.session_state.get('aipost_session_revalidated'):
        return

    try:
        # get_session() lee la cookie/token almacenado por el cliente de Supabase
        session = supabase.auth.get_session()

        if session and session.user:
            mark_aipost_logged_in(session.user)
        else:
            mark_aipost_logged_out()

    except Exception as e:
        # En caso de error de red, etc., asume que no está logueado
        st.error(f"Error al verificar la sesión: {e}")
        mark_aipost_logged_out()

    # Marca que la re-validación se ha hecho en esta ejecución
    st.session_state['aipost_session_revalidated'] = True


def initialize_aipost_session() -> None:
    """Inicializa las variables de sesión específicas de AIPost."""
    aipost_defaults = {
        'aipost_logged_in': False,
        'aipost_session_revalidated': False,
        'user': None,
    }
    for k, v in aipost_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def initialize_supabase_session() -> None:
    """Inicializa las variables de sesión específicas de Supabase (no LinkedIn)."""
    supabase_defaults = {
        'session_revalidated': False,
        'supabase_session_active': False,
    }
    for k, v in supabase_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v