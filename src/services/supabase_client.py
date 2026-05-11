from typing import Optional
from supabase import create_client, Client
import streamlit as st
from src.core.constants import SUPABASE_URL, SUPABASE_KEY

_client: Optional[Client] = None
_admin_client: Optional[Client] = None

#@st.cache_resource
def get_supabase() -> Client:
    """
    Instancia el cliente Supabase de propósito general bajo un patrón Singleton.

    Advertencia: Utilizado principalmente en flujos interactivos. Para rutinas 
    de backend (workers) se debe preferir get_supabase_admin para aislar el contexto.

    :returns: Objeto cliente de Supabase instanciado.
    :raises RuntimeError: Si las credenciales del entorno no están definidas.
    """
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no configurados en el entorno")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Cliente de Supabase creado exitosamente")
    return _client


def get_supabase_admin() -> Client:
    """
    Instancia el cliente Supabase dedicado a queries de datos de backend (Singleton).

    Garantiza el aislamiento de contexto evitando sesiones auth vinculadas, permitiendo
    operaciones headless de base de datos de manera atómica y thread-safe para workers.

    :returns: Objeto admin client de Supabase.
    :raises RuntimeError: Si las credenciales del entorno no están definidas.
    """
    global _admin_client
    if _admin_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no configurados en el entorno")
        _admin_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Cliente ADMIN de Supabase creado exitosamente (sin sesion de auth)")
    return _admin_client
