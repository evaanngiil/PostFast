from typing import Optional
from supabase import create_client, Client
import streamlit as st
from src.core.constants import SUPABASE_URL, SUPABASE_KEY

_client: Optional[Client] = None

#@st.cache_resource
def get_supabase() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no configurados en el entorno")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client created successfully")
    return _client



