from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from src.core.logger import logger
from src.services.supabase_client import get_supabase
from datetime import datetime, timezone

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def get_current_session_data_from_token(token: str | None = Depends(oauth2_scheme)) -> dict:
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