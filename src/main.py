import json
import uuid
import base64 # Para codificar user_info en la URL
from urllib.parse import quote_plus # Para codificar correctamente el token en URL
from fastapi import FastAPI, Request, HTTPException, Depends, Response, Header # Añadir Header
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional # Para Optional Header
from requests_oauthlib import OAuth2Session
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer


# --- Imports ---
try:
    from src.routers.content import content_router
    ROUTERS_LOADED = True
except ImportError as router_err:
    print(f"WARN: Could not import routers: {router_err}") # Usar print aquí ya que el logger puede no estar listo
    ROUTERS_LOADED = False
    content_router = None
    analytics_router = None

from src.core.constants import (
    SECRET_KEY, LI_CLIENT_ID, LI_REDIRECT_URI, BASE_URL, LI_CLIENT_SECRET, DATABASE_URL
)
from src.social_apis import get_linkedin_user_info
from src.core.lifespan import lifespan
from src.core.logger import logger
from src.auth import get_current_session_data_from_token
from src.services.supabase_client import get_supabase
# --- Fin Imports ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False) # auto_error=False para manejar 401 manualmente

# --- FastAPI App Setup ---
app = FastAPI(
    title="PostFast API",
    description="API para el proyecto PostFast con LangGraph",
    lifespan=lifespan # Maneja inicio/apagado, útil para LangGraph state
)

# --- Verify SECRET_KEY ---
if not SECRET_KEY:
    logger.critical("FATAL: SECRET_KEY is not set in constants.py. Application cannot start securely.")
    # En un entorno real, querrías detener la aplicación aquí
    # raise ValueError("SECRET_KEY is not configured.")
    print("WARNING: SECRET_KEY is not set. Using a default insecure key for SessionMiddleware.")
    SECRET_KEY = "default_insecure_secret_key_for_dev_only" # Solo para desarrollo

# Middleware for sessions (CSRF state)
# Asegúrate que `secure=False` y `samesite='lax'` son adecuados para tu entorno (dev vs prod)
# secure=True requiere HTTPS
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=False, same_site='lax')

# Middleware for CORS (Cross-Origin Resource Sharing)
# Permite que Streamlit (en localhost:8501) hable con backend (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"], # Streamlit dev URL
    allow_credentials=True, # Permite cookies y cabeceras de autenticación
    allow_methods=["*"], # Permite todos los métodos HTTP (GET, POST, etc.)
    allow_headers=["*"], # Permite todas las cabeceras
)

# Eliminado: conexiones directas PostgreSQL; usar Supabase

# Session cookie name (identifica la cookie en el navegador)
SESSION_COOKIE_NAME = "postfast_session"


# Eliminado: dependencia local; se usa la de src.auth con Supabase


# --- OAuth Endpoints ---

@app.get("/auth/login/{provider}")
async def oauth_login(provider: str, request: Request):
    logger.info(f"Initiating OAuth login for provider: {provider}")
    client_id = None; redirect_uri = None; scope = None; auth_url = None

    # --- Solo LinkedIn ---
    if provider == "linkedin":
        client_id = LI_CLIENT_ID
        redirect_uri = LI_REDIRECT_URI
        scope = [
            'openid', 'profile', 'email', # Requeridos para /userinfo
            'r_liteprofile', # Perfil básico
            'w_member_social', # Permiso para postear como miembro
            # 'r_member_social', # Permiso para leer posts de miembro
            'r_organization_admin'# Permiso para leer datos de organizaciones admin,
            # 'r_organization_social'
            # 'w_organization_social',
            # 'r_basicprofile' # Permiso para leer perfil básico
        ]
        auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        logger.info(f"Requesting LinkedIn scopes: {scope}")
    else:
        logger.error(f"Unsupported OAuth provider requested: {provider}")
        raise HTTPException(status_code=404, detail="Provider not supported")

    # Validar configuración básica
    if not client_id or not redirect_uri:
         logger.error(f"OAuth client_id or redirect_uri not configured for provider: {provider}")
         raise HTTPException(status_code=500, detail=f"Server configuration error for {provider} login.")

    # Crear sesión OAuth y generar URL de autorización
    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scope)
    authorization_url, state = oauth.authorization_url(auth_url)

    # Guardar el estado CSRF en la sesión del navegador (usando SessionMiddleware)
    request.session['oauth_state'] = state
    logger.debug(f"Generated OAuth state (CSRF): {state} for provider {provider}. Stored in session.")

    # Redirigir al usuario a la página de login/autorización de LinkedIn
    return RedirectResponse(authorization_url, status_code=307)

@app.get("/auth/callback/{provider}")
# Endpoint sigue siendo async, pero las operaciones DB internas son síncronas
async def oauth_callback(provider: str, request: Request, response: Response, code: Optional[str] = None, error: Optional[str] = None, state: Optional[str] = None):
    logger.info(f"Received OAuth callback for {provider}")
    stored_csrf_state = request.session.get('oauth_state')
    redirect_base_url = BASE_URL

    # --- Validaciones ---
    if error: 
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:{error}", status_code=307)
    if not code or not state: 
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:missing_code_or_state", status_code=307)
    if state != stored_csrf_state: 
        request.session.pop('oauth_state', None) 
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:state_mismatch", status_code=307)
    request.session.pop('oauth_state', None); logger.debug("CSRF state validated.")

    try:
        user_info = None; token = None; user_provider_id = None

        # --- Lógica LinkedIn ---
        if provider == "linkedin":
            token_endpoint = "https://www.linkedin.com/oauth/v2/accessToken"
            oauth = OAuth2Session(LI_CLIENT_ID, redirect_uri=LI_REDIRECT_URI, state=state)
            try:
                 token = oauth.fetch_token(token_endpoint, client_secret=LI_CLIENT_SECRET, code=code, include_client_id=True)
            except Exception as token_err: 
                raise Exception(f"Failed to fetch token: {token_err}") from token_err

            if 'access_token' in token: 
                user_info = get_linkedin_user_info(token['access_token'])
            else: 
                raise Exception("Access token missing.")

            if user_info and isinstance(user_info, dict): 
                user_provider_id = user_info.get('sub') or user_info.get('id')
            else: 
                user_info = {}

            if not user_info or not token or not user_provider_id: 
                raise Exception("Incomplete token/user info.")
            logger.info(f"Token/user info fetched for {provider} user {user_provider_id}")

        # --- Guardar Sesión en Supabase ---
        supabase = get_supabase()
        session_cookie_id = uuid.uuid4()
        expires_at = None
        if 'expires_in' in token:
            try:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token['expires_in']))
            except ValueError:
                expires_at = None
        payload = {
            "session_cookie_id": str(session_cookie_id),
            "provider": provider,
            "user_provider_id": user_provider_id,
            "access_token": token.get('access_token'),
            "refresh_token": token.get('refresh_token'),
            "token_type": token.get('token_type'),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "user_info": user_info,
            "last_accessed_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("user_sessions").upsert(payload, on_conflict="user_provider_id,provider").execute()

        # --- Redirigir a Streamlit---
        user_info_json_str = json.dumps(user_info, ensure_ascii=False)
        user_info_b64 = base64.urlsafe_b64encode(user_info_json_str.encode()).decode()
        access_token_encoded = quote_plus(token['access_token'])
        final_redirect_url = f"{redirect_base_url}?auth_provider={provider}&auth_token={access_token_encoded}&user_info={user_info_b64}"
        redirect_response = RedirectResponse(final_redirect_url, status_code=307)
        redirect_response.set_cookie(
            key=SESSION_COOKIE_NAME, value=str(session_cookie_id), # Pasar UUID como string
            httponly=True, secure=False, samesite="lax",
            max_age=3600 * 24 * 7, path="/", domain="localhost"
        )
        return redirect_response

    # --- Manejo de Excepciones --
    except Exception as e:
        logger.exception(f"Critical error during OAuth callback for {provider}: {e}")
        error_code = "callback_failed";
        if isinstance(e, ConnectionError): 
            error_code = "db_error"
        elif "token" in str(e).lower(): 
            error_code = "token_fetch_failed"
        elif "user_info" in str(e).lower(): 
            error_code = "user_info_failed"
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:{error_code}", status_code=307)
    finally:
        # No hay conexiones locales con Supabase que cerrar aquí
        logger.debug("OAuth callback finished.")


@app.get("/auth/me")
async def get_current_user_session(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    session_data = None
    auth_method = "None"
    session_cookie_id_from_browser = None  # Ensure always defined
    supabase = get_supabase()
    try:
            if authorization and authorization.lower().startswith("bearer "):
                token = authorization.split(" ")[1]
                logger.debug(f"[/auth/me] Attempting validation via Bearer token.")
                auth_method = "Bearer"
                result = supabase.table("user_sessions").select("session_cookie_id, provider, user_provider_id, access_token, refresh_token, token_type, expires_at, user_info").eq("access_token", token).single().execute().data
                if result:
                    logger.debug(f"[/auth/me] BEARER token found in Supabase. Result: {result}")
                    # Handle result as a dictionary instead of tuple unpacking
                    session_cookie_id = result['session_cookie_id']
                    provider = result['provider']
                    user_pid = result['user_provider_id']
                    access_token_db = result['access_token']
                    refresh_token = result['refresh_token']
                    t_type = result['token_type']
                    expires_at_db = result['expires_at']
                    user_info_json = result['user_info']

                    token_expired = False
                    if expires_at_db:
                        expires_at_aware = None
                        if isinstance(expires_at_db, datetime):
                            if expires_at_db.tzinfo is None: 
                                expires_at_aware = expires_at_db.replace(tzinfo=timezone.utc)
                            else: 
                                expires_at_aware = expires_at_db
                        else: 
                            logger.warning(f"[/auth/me] expires_at from DB is not datetime: {expires_at_db}")

                        if expires_at_aware and datetime.now(timezone.utc) > expires_at_aware:
                             token_expired = True 
                             logger.warning(f"[/auth/me] Bearer token session {session_cookie_id} expired.")
                    if not token_expired:
                        supabase.table("user_sessions").update({"last_accessed_at": datetime.now(timezone.utc).isoformat()}).eq("session_cookie_id", session_cookie_id).execute()
                        # Handle user_info directly since it's already JSONB from PostgreSQL
                        user_info = user_info_json if isinstance(user_info_json, dict) else {}
                        session_data = { 
                            "authenticated": True, 
                            "provider": provider, 
                            "user_info": user_info,
                            "token_data": { 
                                "access_token": access_token_db, 
                                "refresh_token": refresh_token, 
                                "token_type": t_type,
                                "expires_at": expires_at_db.isoformat() if isinstance(expires_at_db, datetime) else str(expires_at_db) 
                            }
                        }
                        logger.info(f"[/auth/me] Session validated via Bearer token for {provider} user {user_pid}")

            if not session_data:
                session_cookie_id_from_browser = request.cookies.get(SESSION_COOKIE_NAME)
                logger.debug(f"[/auth/me] Checking for session cookie '{SESSION_COOKIE_NAME}'. Found: {'Yes' if session_cookie_id_from_browser else 'No'}")
                if session_cookie_id_from_browser: auth_method = "Cookie"
                if session_cookie_id_from_browser:
                    result = supabase.table("user_sessions").select("provider, user_provider_id, access_token, refresh_token, token_type, expires_at, user_info").eq("session_cookie_id", session_cookie_id_from_browser).single().execute().data
                    if not result:
                        logger.warning(f"[/auth/me] Session cookie ID '{session_cookie_id_from_browser}' found but no matching session in DB.")
                        response = Response(content=json.dumps({"authenticated": False, "reason": "Session not found in DB"}), media_type="application/json", status_code=200)
                        response.delete_cookie(SESSION_COOKIE_NAME, path="/", domain="localhost"); 
                        return response
                    provider, user_pid, access_token, refresh_token, t_type, expires_at_db, user_info_json = result
                    token_expired = False

                    if expires_at_db:
                        expires_at_aware = None
                        if isinstance(expires_at_db, datetime):
                            if expires_at_db.tzinfo is None: 
                                expires_at_aware = expires_at_db.replace(tzinfo=timezone.utc)
                            else: 
                                expires_at_aware = expires_at_db
                        else: 
                            logger.warning(f"[/auth/me] expires_at from DB (cookie) is not datetime: {expires_at_db}")
                        if expires_at_aware and datetime.now(timezone.utc) > expires_at_aware:
                            token_expired = True; logger.warning(f"[/auth/me] Session {session_cookie_id_from_browser} via cookie expired.")
                    if token_expired:
                        response = Response(content=json.dumps({"authenticated": False, "reason": "Token expired"}), media_type="application/json", status_code=200) 
                        return response

                    supabase.table("user_sessions").update({"last_accessed_at": datetime.now(timezone.utc).isoformat()}).eq("session_cookie_id", session_cookie_id_from_browser).execute()
                    try:
                        user_info = json.loads(user_info_json) if user_info_json else {}
                    except Exception as json_err:
                        logger.warning(f"[/auth/me] Could not decode user_info_json: {json_err}")
                        user_info = {}

                    session_data = { 
                        "authenticated": True, 
                        "provider": provider,
                        "user_info": user_info,
                        "token_data": 
                            { "access_token": access_token,
                             "refresh_token": refresh_token, 
                             "token_type": t_type,
                             "expires_at": expires_at_db.isoformat() if isinstance(expires_at_db, datetime) else expires_at_db 
                            }
                        }
                    logger.info(f"[/auth/me] Session validated via Cookie for {provider} user {user_pid}")
    except Exception as e: logger.exception(f"[/auth/me] Error checking cookie session {session_cookie_id_from_browser}: {e}"); session_data = None

    if session_data:
        logger.debug(f"[/auth/me] Returning authenticated session data (validated via {auth_method})."); return session_data
    else:
        reason = "No valid session found via token or cookie";
        if auth_method == "Bearer": 
            reason = "Bearer token invalid/expired or session not found"
        elif auth_method == "Cookie": 
            reason = "Cookie invalid, session expired, or session not found"
        logger.debug(f"[/auth/me] Returning not authenticated (method attempted: {auth_method}). Reason: {reason}"); return {"authenticated": False, "reason": reason}


@app.get("/auth/logout")
async def logout_user(request: Request):
    session_cookie_id = request.cookies.get(SESSION_COOKIE_NAME)
    logger.info(f"Logout requested. Session cookie ID found: {bool(session_cookie_id)}")
    if session_cookie_id:
        try:
            supabase = get_supabase()
            result = supabase.table("user_sessions").delete().eq("session_cookie_id", session_cookie_id).execute()
            rows = len(result.data) if result and getattr(result, 'data', None) else 0
            logger.info(f"Session deleted from Supabase for cookie ID: {session_cookie_id}. Rows affected: {rows}")
        except Exception as e:
            logger.error(f"Error deleting session from Supabase: {e}", exc_info=True)

    # Redirigir y borrar cookie
    response = RedirectResponse(url=BASE_URL, status_code=307)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/", domain="localhost")
    return response

# --- Endpoints básicos y Routers ---

@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    html_content = """<html><head><title>Privacy Policy</title></head><body><h1>Privacy Policy</h1><p>This is a placeholder privacy policy...</p></body></html>"""
    return HTMLResponse(content=html_content)

@app.get("/")
async def root():
    logger.info("Root endpoint '/' accessed.")
    return {"message": "AIPost Backend API is running!"}

# --- Incluir Routers (protegidos con la dependencia de autenticación) ---
if ROUTERS_LOADED:
    try:
        # Aplicar la dependencia get_current_session_data_from_token a todos los endpoints
        # dentro de estos routers.
        app.include_router(
            content_router,
            prefix="/content",
            dependencies=[Depends(get_current_session_data_from_token)] # Aplicar dependencia
        )
        # Analytics router eliminado
        logger.info("✅ Routers included successfully with authentication dependency.")
    except Exception as e:
        logger.error(f"❌ Error including routers: {e}", exc_info=True)
else:
    logger.warning("Skipping router inclusion because they failed to import.")