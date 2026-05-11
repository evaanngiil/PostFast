from src.core.logger import logger 
from src.services.supabase_client import get_supabase_admin as get_supabase

def setup_database():
    """
    Despliega o verifica la estructura relacional base mediante invocación de funciones RPC en PostgreSQL.

    :returns: None
    """
    try:
        supabase = get_supabase()
        try:
            res = supabase.rpc("ensure_schema").execute()
            logger.info(f"ensure_schema RPC executed. Result: {getattr(res, 'data', None)}")
        except Exception as rpc_err:
            logger.warning("RPC 'ensure_schema' no disponible: %s", rpc_err)
    except Exception as e:
        logger.error(f"Supabase initialization failed: {e}")
