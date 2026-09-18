"""
Configuración compartida de los tests de AIPost.

Fija variables de entorno ANTES de cualquier import del código de src/ para que
los módulos con configuración a nivel de import (constants, clientes) funcionen
sin credenciales reales ni servicios externos.
"""
import os

os.environ.setdefault("AIPOST_CHECKPOINTER", "memory")
os.environ.setdefault("GENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test-key-not-real")
os.environ.setdefault("SUPABASE_CONN_STRING", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("BASE_URL", "http://localhost:8501")
os.environ.setdefault("FASTAPI_URL", "http://localhost:8000")
