import json
import uuid
import base64
from urllib.parse import quote_plus
from fastapi import FastAPI, Request, HTTPException, Depends, Response, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from requests_oauthlib import OAuth2Session
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer

# --- Imports ---
try:
    from src.routers.content import content_router
    ROUTERS_LOADED = True
except ImportError as router_err:
    print(f"WARN: Could not import routers: {router_err}")
    ROUTERS_LOADED = False
    content_router = None

from src.core.constants import (
    SECRET_KEY, LI_CLIENT_ID, LI_REDIRECT_URI, BASE_URL, LI_CLIENT_SECRET
)
from src.social_apis import get_linkedin_user_info
from src.core.lifespan import lifespan
from src.core.logger import logger
from src.linkedin_auth import get_current_session_data_from_token
from src.services.supabase_client import get_supabase
# --- Fin Imports ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# --- FastAPI App Setup ---
app = FastAPI(
    title="AIPost API",
    description="API para el proyecto AIPost",
    lifespan=lifespan
)

# --- Middleware ---
if not SECRET_KEY:
    logger.critical("FATAL: SECRET_KEY is not set. Using a default insecure key.")
    SECRET_KEY = "default_insecure_secret_key_for_dev_only"

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=False, same_site='lax')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
SESSION_COOKIE_NAME = "postfast_session"


# --- OAuth Endpoints ---

@app.get("/auth/login/{provider}")
async def oauth_login(provider: str, request: Request, create_platform_session: Optional[str] = None):
    logger.info(f"Initiating OAuth login for provider: {provider}")
    
    if provider == "linkedin":
        client_id = LI_CLIENT_ID
        redirect_uri = LI_REDIRECT_URI
        scope = ['openid', 'profile', 'email', 'r_liteprofile', 'w_member_social', 'r_organization_admin']
        auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        logger.info(f"Requesting LinkedIn scopes: {scope}")
    else:
        raise HTTPException(status_code=404, detail="Provider not supported")

    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scope)
    authorization_url, state = oauth.authorization_url(auth_url)

    request.session['oauth_state'] = state
    # Guardar el parámetro en la sesión para recuperarlo en el callback
    if create_platform_session:
        request.session['create_platform_session'] = create_platform_session
    
    logger.debug(f"Generated OAuth state: {state}. Stored in session.")
    return RedirectResponse(authorization_url, status_code=307)


@app.get("/auth/callback/{provider}")
async def oauth_callback(provider: str, request: Request, code: Optional[str] = None, error: Optional[str] = None, state: Optional[str] = None):
    logger.info(f"Received OAuth callback for {provider}")
    
    # --- Validaciones ---
    stored_csrf_state = request.session.get('oauth_state')
    # ---Recuperar el valor de la sesión
    create_platform_session = request.session.pop('create_platform_session', None)
    redirect_base_url = BASE_URL

    if error: return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:{error}", status_code=307)
    if not code or not state: return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:missing_code_or_state", status_code=307)
    if state != stored_csrf_state:
        request.session.pop('oauth_state', None)
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:state_mismatch", status_code=307)
    
    request.session.pop('oauth_state', None)
    logger.debug("CSRF state validated.")

    try:
        user_info = None; token = None; user_provider_id = None

        if provider == "linkedin":
            token_endpoint = "https://www.linkedin.com/oauth/v2/accessToken"
            oauth = OAuth2Session(LI_CLIENT_ID, redirect_uri=LI_REDIRECT_URI, state=state)
            token = oauth.fetch_token(token_endpoint, client_secret=LI_CLIENT_SECRET, code=code, include_client_id=True)
            user_info = get_linkedin_user_info(token['access_token'])
            user_provider_id = user_info.get('sub') if user_info else None
            if not user_info or not token or not user_provider_id:
                raise Exception("Incomplete token/user info.")
            logger.info(f"Token/user info fetched for {provider} user {user_provider_id}")

        # --- Guardar Sesión en Supabase ---
        supabase = get_supabase()
        session_cookie_id = uuid.uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token.get('expires_in', 3600)))
        payload = {
            "session_cookie_id": str(session_cookie_id), "provider": provider,
            "user_provider_id": user_provider_id, "access_token": token.get('access_token'),
            "refresh_token": token.get('refresh_token'), "token_type": token.get('token_type'),
            "expires_at": expires_at.isoformat(), "user_info": user_info,
            "last_accessed_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("user_sessions").upsert(payload, on_conflict="user_provider_id,provider").execute()

        # --- Redirigir a Streamlit---
        user_info_b64 = base64.urlsafe_b64encode(json.dumps(user_info).encode()).decode()
        user_info_encoded = quote_plus(user_info_b64)  # Codificar user_info para la URL
        access_token_encoded = quote_plus(token['access_token'])
        
        #  Usar la variable codificada en la URL
        final_redirect_url = f"{redirect_base_url}?auth_provider={provider}&auth_token={access_token_encoded}&user_info={user_info_encoded}"
        if create_platform_session:
            final_redirect_url += f"&create_platform_session={create_platform_session}"

        redirect_response = RedirectResponse(final_redirect_url, status_code=307)
        redirect_response.set_cookie(
            key=SESSION_COOKIE_NAME, value=str(session_cookie_id),
            httponly=True, secure=False, samesite="lax", max_age=3600 * 24 * 7, path="/"
        )
        return redirect_response

    except Exception as e:
        logger.exception(f"Critical error during OAuth callback for {provider}: {e}")
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:callback_failed", status_code=307)
    finally:
        logger.debug("OAuth callback finished.")


@app.get("/auth/me")
async def get_current_user_session(request: Request, authorization: Optional[str] = Header(None)):
    session_data = None
    auth_method = "None"
    session_cookie_id = None
    supabase = get_supabase()
    result = None

    try:
        # Prioridad 1: Cabecera Bearer
        if authorization and authorization.lower().startswith("Bearer "):
            token = authorization.split(" ")[1]
            auth_method = "Bearer"
            logger.debug(f"[/auth/me] Attempting validation via Bearer token.")
            result = supabase.table("user_sessions").select("*").eq("access_token", token).maybe_single().execute().data
            if result:
                session_cookie_id = result.get('session_cookie_id')
        
        # Prioridad 2: Cookie de sesión
        if not session_cookie_id:
            cookie_from_browser = request.cookies.get(SESSION_COOKIE_NAME)
            if cookie_from_browser:
                auth_method = "Cookie"
                logger.debug(f"[/auth/me] Attempting validation via Cookie: {cookie_from_browser}")
                result = supabase.table("user_sessions").select("*").eq("session_cookie_id", cookie_from_browser).maybe_single().execute().data
                if result:
                    session_cookie_id = result.get('session_cookie_id')
                else:
                    logger.warning(f"[/auth/me] Cookie ID '{cookie_from_browser}' found but no matching session in DB.")
                    response = Response(content=json.dumps({"authenticated": False, "reason": "Session not found"}), media_type="application/json")
                    response.delete_cookie(SESSION_COOKIE_NAME) 
                    return response

        
        if 'result' in locals() and result:
            expires_at_db = result.get('expires_at')
            token_expired = False
            if expires_at_db:
                try:
                    expires_at_aware = datetime.fromisoformat(expires_at_db.replace('Z', '+00:00'))
                    if expires_at_aware.tzinfo is None:
                        expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > expires_at_aware:
                        token_expired = True
                        logger.warning(f"[/auth/me] Session {session_cookie_id} expired.")
                except (ValueError, TypeError):
                    logger.warning(f"[/auth/me] Could not parse expires_at: {expires_at_db}")

            if not token_expired:
                supabase.table("user_sessions").update({"last_accessed_at": datetime.now(timezone.utc).isoformat()}).eq("session_cookie_id", session_cookie_id).execute()
                
                user_info = result.get('user_info', {})
                if not isinstance(user_info, dict): user_info = {}

                session_data = {
                    "authenticated": True, "provider": result.get('provider'), "user_info": user_info,
                    "token_data": {
                        "access_token": result.get('access_token'), "refresh_token": result.get('refresh_token'),
                        "token_type": result.get('token_type'), "expires_at": expires_at_db
                    }
                }
                logger.info(f"[/auth/me] Session validated via {auth_method} for {result.get('provider')} user {result.get('user_provider_id')}")
        
    except Exception as e:
        logger.exception(f"[/auth/me] Error checking session: {e}")
        session_data = None

    if session_data:
        return session_data
    else:
        reason = f"No valid session found (method attempted: {auth_method})"
        return {"authenticated": False, "reason": reason}


@app.get("/auth/logout")
async def logout_user(request: Request):
    session_cookie_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_cookie_id:
        try:
            supabase = get_supabase()
            supabase.table("user_sessions").delete().eq("session_cookie_id", session_cookie_id).execute()
            logger.info(f"Session deleted from Supabase for cookie ID: {session_cookie_id}")
        except Exception as e:
            logger.error(f"Error deleting session from Supabase: {e}")

    response = RedirectResponse(url=BASE_URL, status_code=307)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return response

@app.get("/")
async def root():
    return {"message": "AIPost Backend API is running!"}

if ROUTERS_LOADED:
    app.include_router(
        content_router,
        prefix="/content",
        dependencies=[Depends(get_current_session_data_from_token)]
    )
    logger.info("✅ Routers included successfully.")