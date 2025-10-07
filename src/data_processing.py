## Eliminado psycopg; este módulo ya no abre conexiones directas

from src.core.constants import DATABASE_URL
from src.core.logger import logger 
from src.services.supabase_client import get_supabase

def get_db_connection(read_only: bool = False):
    """Deprecado: sin uso tras migración a Supabase."""
    logger.warning("get_db_connection is deprecated after migration to Supabase.")
    return None

def setup_database():
    """Asegura el esquema llamando a un RPC en Supabase (ensure_schema)."""
    try:
        supabase = get_supabase()
        # Intentar invocar un RPC que crea tablas si no existen
        try:
            res = supabase.rpc("ensure_schema").execute()
            logger.info(f"ensure_schema RPC executed. Result: {getattr(res, 'data', None)}")
        except Exception as rpc_err:
            # Si el RPC no existe, dejar mensaje claro para crear la función en Supabase
            logger.warning(
                "Supabase RPC 'ensure_schema' no encontrado o falló. "
                "Crea la función SQL en tu proyecto Supabase usando el SQL que proporcionaré en README/nota, "
                "y vuelve a ejecutar. Error: %s", rpc_err
            )
    except Exception as e:
        logger.error(f"Supabase initialization failed: {e}")



# --- Load and Transform Functions (ELT) ---
def setup_database():
    """Asegura el esquema base necesario en Supabase (no analytics)."""
    try:
        supabase = get_supabase()
        # Mantener RPC de ensure_schema si existe; es opcional
        try:
            res = supabase.rpc("ensure_schema").execute()
            logger.info(f"ensure_schema RPC executed. Result: {getattr(res, 'data', None)}")
        except Exception as rpc_err:
            logger.warning("RPC 'ensure_schema' no disponible: %s", rpc_err)
    except Exception as e:
        logger.error(f"Supabase initialization failed: {e}")


## Todas las funciones de transformación/carga de Analytics eliminadas




# --- Query Functions for Dashboards ---





