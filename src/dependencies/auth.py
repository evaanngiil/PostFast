from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from src.core.logger import logger
from src.core.constants import DEMO_MODE
from src.services.supabase_client import get_supabase_admin as get_supabase
from datetime import datetime, timezone

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def get_current_session_data_from_token(token: str | None = Depends(oauth2_scheme)) -> dict:
    """
    Verifica el token Bearer provisto y recupera la sesión autenticada.

    :param token: JWT o cadena de acceso provista en el header Authorization.
    :returns: Diccionario estructurado con la data de la sesión extraída de la BD.
    :raises HTTPException: Status 401 si el token expiró, es inválido o no se proveyó.
    """
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # MODO DEMO DEL TFG: permite evaluar la aplicación localmente sin credenciales
    # de LinkedIn. Solo se acepta si AIPOST_DEMO_MODE=true en el entorno; en caso
    # contrario los tokens 'mock_*' se tratan como credenciales inválidas.
    if DEMO_MODE and (token == "mock_token_tfg" or token.startswith("mock_")):
        logger.info(f"[Auth Dependency] Iniciando sesión en MODO SIMULACIÓN TFG con token: {token}")
        return {
            "authenticated": True,
            "provider": "linkedin",
            "user_info": {
                "id": "mock_user_123",
                "name": "Profesor Evaluador TFG",
                "email": "evaluador@universidad.edu",
                "localizedFirstName": "Profesor",
                "localizedLastName": "Evaluador"
            },
            "user_provider_id": "mock_user_123",
            "session_cookie_id": "mock_cookie_123",
            "token_data": {
                "access_token": token,
                "refresh_token": "mock_refresh_token",
                "expires_at": "2030-01-01T00:00:00+00:00"
            }
        }

    import time

    result = None
    linkedin_access_token = None
    max_retries = 3

    for attempt in range(max_retries):
        try:
            supabase = get_supabase()
            resp = supabase.table("user_sessions").select("*").eq("access_token", token).execute()
            result = resp.data[0] if resp.data else None
            if not result:
                resp = supabase.table("user_sessions").select("*").eq("session_cookie_id", token).execute()
                result = resp.data[0] if resp.data else None

            if result and result.get('provider') == 'supabase':
                user_provider_id = result.get('user_provider_id')
                li_resp = supabase.table("user_sessions").select("access_token").eq("user_provider_id", user_provider_id).eq("provider", "linkedin").execute()
                if li_resp.data:
                    linkedin_access_token = li_resp.data[0].get("access_token")
            break
        except Exception as e:
            error_str = str(e).lower()
            if "disconnected" in error_str or "connection" in error_str or "pool" in error_str or "timeout" in error_str or "server disconnected" in error_str or "protocol" in error_str:
                logger.warning(f"[Dependency] Error de conexión con Supabase (intento {attempt + 1}/{max_retries}): {e}. Recreando cliente...")
                try:
                    import src.services.supabase_client as sb_mod
                    sb_mod._admin_client = None
                    sb_mod._client = None
                except Exception:
                    pass
                time.sleep(0.25 * (attempt + 1))
            else:
                if isinstance(e, HTTPException):
                    raise e
                logger.exception(f"[Dependency] Error no recuperable verificando token: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
    else:
        logger.error("[Dependency] Se agotaron los reintentos de conexión con Supabase.")
        raise HTTPException(status_code=500, detail="Internal server error")

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
        "linkedin_access_token": linkedin_access_token,
        "token_data": {
            "access_token": result.get('access_token'), "refresh_token": result.get('refresh_token'),
            "token_type": result.get('token_type'), "expires_at": expires_at_db
        }
    }
