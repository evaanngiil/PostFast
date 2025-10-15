import streamlit as st
from supabase import AuthApiError
from typing import Optional
import requests

from src.core.logger import logger
from src.core.constants import FASTAPI_URL
from src.services.supabase_client import get_supabase

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

# -- helpers de estado de AIPost --
def mark_aipost_logged_in(user: object) -> None:
    """Marca al usuario como logueado en AIPost y guarda el objeto user."""
    st.session_state['aipost_logged_in'] = True
    st.session_state['user'] = user

def mark_aipost_logged_out() -> None:
    """Marca al usuario como no logueado en AIPost y limpia la info de usuario."""
    st.session_state['aipost_logged_in'] = False
    st.session_state['user'] = None
    # Limpiamos también el token unificado
    st.session_state['auth_token_for_url'] = None

def is_aipost_logged_in() -> bool:
    """Comprueba si hay un usuario logueado en AIPost."""
    return bool(st.session_state.get('aipost_logged_in'))

def get_aipost_user() -> Optional[object]:
    """Devuelve el objeto user almacenado para AIPost o None."""
    return st.session_state.get('user')

def get_user_from_supabase_token(jwt: str):
    try:
        supabase = get_supabase()
        # La librería de Supabase puede validar un JWT y devolver el usuario asociado
        user_response = supabase.auth.get_user(jwt)
        return user_response.user
    except Exception:
        return None

def get_user_from_supabase_token(jwt: str):
    try:
        supabase = get_supabase()
        # La librería de Supabase puede validar un JWT y devolver el usuario asociado
        user_response = supabase.auth.get_user(jwt)
        return user_response.user
    except Exception:
        return None


def login(email: str, password: str) -> bool:
    """Inicia sesión, obtiene un token unificado del backend y lo guarda."""
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user and response.session:
            mark_aipost_logged_in(response.user)
            logger.info("Login de Supabase exitoso.")
            return True
        else:
            st.warning("Credenciales incorrectas. Por favor, inténtalo de nuevo.")
            return False
    except AuthApiError as e:
        st.error(f"Error de autenticación: {e.message}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado durante el login: {e}")
        st.error("Ocurrió un error de conexión. Inténtalo de nuevo más tarde.")
        return False


def logout() -> None:
    """Cierra sesión en Supabase, en el backend y limpia todo el session_state."""
    try:
        supabase.auth.sign_out()
    except Exception as e:
        logger.error(f"Error en Supabase sign_out: {e}")

    # Limpiar todo el estado de sesión para asegurar un inicio limpio
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        del st.session_state[key]

    # Limpiar query params
    st.query_params.clear()

    # Llamar al logout del backend (best-effort)
    try:
        requests.get(f"{FASTAPI_URL}/auth/logout", timeout=5)
        logger.info("Llamada al endpoint de logout del backend realizada.")
    except Exception as e:
        logger.warning(f"No se pudo llamar al logout del backend: {e}")

    # Forzar la recarga para volver a la página de login
    st.rerun()


def revalidate_aipost_session() -> None:
    """
    Comprueba si hay una sesión de Supabase activa y actualiza st.session_state.
    Se usa como una sincronización secundaria, la fuente de verdad principal es el token.
    """
    if st.session_state.get('aipost_session_revalidated'):
        return

    try:
        session = supabase.auth.get_session()
        if session and session.user and not is_aipost_logged_in():
            # Si hay sesión de Supabase pero no de AIPost, la marcamos.
            # Esto puede pasar en la primera carga si hay una cookie de Supabase válida.
            mark_aipost_logged_in(session.user)
            logger.debug("Revalidación de Supabase encontró una sesión activa.")
        elif not session or not session.user:
            # Si no hay sesión de Supabase, nos aseguramos de que esté marcado como logged out.
            mark_aipost_logged_out()

    except Exception as e:
        st.error(f"Error al verificar la sesión de Supabase: {e}")
        mark_aipost_logged_out()

    st.session_state['aipost_session_revalidated'] = True