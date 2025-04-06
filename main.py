# main.py

import json
import uuid
import base64 # Para codificar user_info en la URL
from urllib.parse import quote_plus # Para codificar correctamente
from fastapi import FastAPI, Request, HTTPException, Depends, Response, Header # Añadir Header
from typing import Optional # Para Optional Header
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from requests_oauthlib import OAuth2Session
import duckdb
from datetime import datetime, timedelta, timezone
import requests
from fastapi.security import OAuth2PasswordBearer # Para autenticación Bearer

# --- Imports ---
from src.routers.content import content_router
from src.routers.analytics import analytics_router
from src.core.constants import (
    SECRET_KEY, FB_CLIENT_ID, FB_REDIRECT_URI, LI_CLIENT_ID,
    LI_REDIRECT_URI, BASE_URL, FB_CLIENT_SECRET, LI_CLIENT_SECRET
)
from src.social_apis import  get_linkedin_user_info
from src.core.lifespan import lifespan
from src.core.logger import logger
from src.auth import get_current_session_data_from_token # Asegúrate que esta función esté definida

# --- Fin Imports ---

# --- Verify SECRET_KEY ---
app = FastAPI(
    title="PostFast API",
    description="API para el proyecto PostFast con LangGraph",
    lifespan=lifespan
)

# Middleware for sessions (CSRF state)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=False) # Mantenido para CSRF
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit URL
    allow_credentials=True, # Importante para cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection setup
DB_FILE = "analytics.duckdb"
def get_db_connection():
    """Get a connection to the DuckDB database."""
    try:
        conn = duckdb.connect(database=DB_FILE, read_only=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_cookie_id VARCHAR PRIMARY KEY,
                provider VARCHAR NOT NULL,
                user_provider_id VARCHAR NOT NULL,
                access_token VARCHAR NOT NULL,
                refresh_token VARCHAR,
                token_type VARCHAR,
                expires_at TIMESTAMP,
                user_info TEXT,
                created_at TIMESTAMP DEFAULT current_timestamp,
                last_accessed_at TIMESTAMP DEFAULT current_timestamp
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_provider_id ON user_sessions (user_provider_id, provider);")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect/setup DB '{DB_FILE}': {e}", exc_info=True)
        return None

# Session cookie name (sigue siendo útil para /auth/me si se llama desde el navegador)
SESSION_COOKIE_NAME = "postfast_session"


# --- OAuth Endpoints ---
@app.get("/auth/login/{provider}")
# ... (sin cambios) ...
async def oauth_login(provider: str, request: Request):
    logger.info(f"Initiating OAuth login for provider: {provider}")
    client_id = None; redirect_uri = None; scope = None; auth_url = None

    if provider == "facebook":
        client_id = FB_CLIENT_ID; 
        redirect_uri = FB_REDIRECT_URI
        scope = ["public_profile", "email", "pages_show_list", "pages_read_engagement","read_insights", "pages_manage_posts"]
        auth_url = "https://www.facebook.com/v18.0/dialog/oauth"
    elif provider == "linkedin":
        client_id = LI_CLIENT_ID; redirect_uri = LI_REDIRECT_URI
        # --- VERIFICAR SCOPES ---
        # Asegurar que openid, profile, email (para /userinfo)
        # y w_member_social, r_organization_admin (para acciones) están presentes.
        scope = [
            'openid', 'profile', 'email', # Requeridos para /userinfo
            'r_liteprofile', # Perfil básico (puede ser redundante con 'profile')
            'w_member_social', # Permiso para postear como miembro (necesario para /ugcPosts)
            'r_organization_admin' # Permiso para leer datos de organizaciones y sus stats
        ]
        auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        logger.info(f"Requesting LinkedIn scopes: {scope}")

    else:
        raise HTTPException(status_code=404, detail="Provider not supported")

    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scope)
    authorization_url, state = oauth.authorization_url(auth_url)
    request.session['oauth_state'] = state
    logger.debug(f"Generated OAuth state (CSRF): {state} for provider {provider}")
    return RedirectResponse(authorization_url, status_code=307)


@app.get("/auth/callback/{provider}")
async def oauth_callback(provider: str, request: Request, response: Response, code: str = None, error: str = None, state: str = None):
    logger.info(f"Received OAuth callback for {provider}")
    stored_csrf_state = request.session.get('oauth_state')
    logger.debug(f"Callback state: {state}, Stored CSRF state: {stored_csrf_state}")
    redirect_base_url = BASE_URL

    if error: 
        logger.error(f"OAuth callback error: {error}"); return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:{error}", status_code=307)
    if not code or not state: 
        logger.error("Missing code or state"); return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:missing_code_or_state", status_code=307)
    if state != stored_csrf_state: 
        logger.error(f"CSRF state mismatch"); return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:state_mismatch", status_code=307)

    request.session.pop('oauth_state', None); logger.debug("CSRF state validated and popped.")

    conn = None
    try:
        user_info = None; token = None; user_provider_id = None

        if provider == "linkedin":
            token_endpoint = "https://www.linkedin.com/oauth/v2/accessToken"
            oauth = OAuth2Session(LI_CLIENT_ID, redirect_uri=LI_REDIRECT_URI, state=state)
            logger.debug(f"Fetching LinkedIn token from: {token_endpoint}")
            try:
                 token = oauth.fetch_token(
                    token_endpoint,
                    client_secret=LI_CLIENT_SECRET,
                    code=code,
                    include_client_id=True # LinkedIn a menudo requiere esto
                 )
                 logger.debug(f"LinkedIn token fetched successfully. Keys: {token.keys()}")
            except Exception as token_err:
                 logger.exception("Error fetching LinkedIn token.")
                 raise Exception(f"Failed to fetch token: {token_err}") from token_err

            # Usar la función corregida para obtener user info via /userinfo
            user_info = get_linkedin_user_info(token['access_token'])
            logger.debug(f"LinkedIn user_info received from get_linkedin_user_info: {user_info}")

            # Extraer ID de 'sub' (más fiable con /userinfo)
            if user_info and isinstance(user_info, dict):
                 user_provider_id = user_info.get('sub') # Priorizar 'sub'
                 if not user_provider_id:
                      logger.warning("LinkedIn user info missing 'sub' field, attempting 'id' as fallback.")
                      user_provider_id = user_info.get('id')
            else:
                 logger.error("LinkedIn user_info is missing, None, or not a dictionary after API call.")
                 # Establecer user_info a un dict vacío para evitar errores posteriores si es None
                 user_info = {}

            # --- Check crucial ---
            if not user_info or not token or not user_provider_id:
                missing_parts = []
                # Refinar log de partes faltantes
                if not user_info: missing_parts.append("user_info (from API call)")
                if not token: missing_parts.append("token (from fetch_token)")
                if not user_provider_id: missing_parts.append("user_provider_id ('sub' field in user_info)")
                error_message = f"Incomplete token/user info obtained. Missing/Invalid: {', '.join(missing_parts)}"
                logger.error(error_message)
                raise Exception(error_message) # Lanzar excepción para que se maneje abajo

            logger.info(f"Token and user info fetched successfully for {provider}. User ID ('sub'): {user_provider_id}")

        # --- Crear y Guardar Sesión Segura en BD ---
        conn = get_db_connection()
        if not conn: 
            raise Exception("Database connection failed.")

        session_cookie_id = str(uuid.uuid4()) # ID para la cookie/DB
        expires_at = None
        if 'expires_in' in token:
            try: 
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token['expires_in']))
            except: 
                expires_at = None
        user_info_json = json.dumps(user_info)

        # Guardar en BD (sin cambios)
        conn.execute("""
            INSERT OR REPLACE INTO user_sessions (
                session_cookie_id, provider, user_provider_id, access_token, refresh_token,
                token_type, expires_at, user_info, last_accessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
        """, [
            session_cookie_id, provider, user_provider_id, token['access_token'],
            token.get('refresh_token'), token.get('token_type'),
            expires_at, user_info_json
        ])
        logger.info(f"User session stored/updated in DB with session_cookie_id: {session_cookie_id}")

        # --- Establecer la Cookie (¡Todavía útil!) ---
        # Esta cookie permite que /auth/me funcione si el navegador la envía
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_cookie_id,
            httponly=True,
            secure=False,  # TODO: Set True in production (HTTPS)
            samesite="lax",
            max_age=3600 * 24 * 7, # Extend cookie life (e.g., 1 week)
            path="/",
            domain="localhost" # TODO: Set production domain
        )
        logger.debug(f"Secure session cookie '{SESSION_COOKIE_NAME}' set for potential browser use.")

        # --- !! NUEVO: Redirigir a Streamlit con Token e Info en Query Params !! ---
        # Codificar user_info para pasarlo de forma segura en la URL
        user_info_b64 = base64.urlsafe_b64encode(user_info_json.encode()).decode()
        # Codificar token por si tiene caracteres especiales
        access_token_encoded = quote_plus(token['access_token'])

        # Construir la URL de redirección con los parámetros
        final_redirect_url = f"{redirect_base_url}?auth_provider={provider}&auth_token={access_token_encoded}&user_info={user_info_b64}"

        # Asegurarse de que la respuesta es la de RedirectResponse para que set_cookie funcione
        redirect_response = RedirectResponse(final_redirect_url, status_code=307)

        # Re-aplicar la cookie a la respuesta de redirección
        redirect_response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_cookie_id,
            httponly=True,
            secure=False, # TODO: Set True in production (HTTPS)
            samesite="lax",
            max_age=3600 * 24 * 7, # 1 week
            path="/",
            domain="localhost" # TODO: Set production domain
        )
        return redirect_response

    # --- Manejo de Excepciones (redirigir con error) ---
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Network error: {req_err}", exc_info=True)
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:network_error", status_code=307)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as data_err:
        logger.error(f"Data/DB error: {data_err}", exc_info=True)
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:data_processing_error", status_code=307)
    except Exception as e:
        logger.exception(f"Error during OAuth callback for {provider}: {e}")
        # Usar un código de error genérico o el mensaje de la excepción (con cuidado)
        error_code = "callback_failed"
        # Podríamos intentar ser más específicos si la excepción lo permite
        if "token" in str(e).lower(): 
            error_code = "token_fetch_failed"
        elif "user_info" in str(e).lower(): 
            error_code = "user_info_failed"

        # Redirigir con el error
        return RedirectResponse(f"{redirect_base_url}?auth_error={provider}:{error_code}", status_code=307)
    finally:
        if conn: 
            conn.close()
            logger.debug("DB connection closed.")


@app.get("/auth/me")
async def get_current_user_session(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Verifica la sesión del usuario (Bearer o Cookie).
    Devuelve los datos del usuario si es válida. MANEJO DE CONEXIÓN CORREGIDO.
    """
    session_data = None
    auth_method = "None"
    conn = None # Inicializar conexión como None

    try: # Envolver toda la lógica en un try para usar finally
        # 1. Intentar validar con Token Bearer
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ")[1]
            logger.debug(f"[/auth/me] Attempting validation via Bearer token.")
            auth_method = "Bearer"
            # try anidado solo para la lógica específica del bearer, el finally externo cierra la conexión
            try:
                conn = get_db_connection() # Abrir conexión aquí
                if not conn: raise HTTPException(status_code=503, detail="Database unavailable")

                result = conn.execute("""
                    SELECT session_cookie_id, provider, user_provider_id, access_token, refresh_token,
                           token_type, expires_at, user_info
                    FROM user_sessions
                    WHERE access_token = ?
                """, (token,)).fetchone()

                if result:
                    (session_cookie_id, provider, user_pid, access_token_db, refresh_token,
                     t_type, expires_at_db, user_info_json) = result

                    # --- CORRECCIÓN DATETIME (como antes) ---
                    token_expired = False
                    if expires_at_db:
                        if isinstance(expires_at_db, datetime) and expires_at_db.tzinfo is None:
                            expires_at_aware = expires_at_db.replace(tzinfo=timezone.utc)
                        elif isinstance(expires_at_db, datetime):
                             expires_at_aware = expires_at_db
                        else: expires_at_aware = None

                        if expires_at_aware and datetime.now(timezone.utc) > expires_at_aware:
                             token_expired = True
                             logger.warning(f"[/auth/me] Bearer token associated with session {session_cookie_id} is expired.")
                    # --- FIN CORRECCIÓN DATETIME ---

                    if not token_expired:
                        conn.execute("UPDATE user_sessions SET last_accessed_at = current_timestamp WHERE session_cookie_id = ?", (session_cookie_id,))
                        user_info = json.loads(user_info_json) if user_info_json else {}
                        session_data = { # ... (datos de sesión como antes) ...
                            "authenticated": True, "provider": provider, "user_info": user_info,
                            "token_data": {
                                "access_token": access_token_db, "refresh_token": refresh_token, "token_type": t_type,
                                "expires_at": expires_at_db.isoformat() if isinstance(expires_at_db, datetime) else expires_at_db
                            }
                        }
                        logger.info(f"[/auth/me] Session validated via Bearer token for {provider} user {user_pid}")
                    # Si expiró, session_data sigue None, se intentará con cookie

            except Exception as e:
                logger.error(f"[/auth/me] Error during Bearer token validation: {e}", exc_info=True)
                # No lanzar error aquí, permitir que intente con cookie

        # 2. Si no se validó con token, intentar con Cookie
        if not session_data:
            cookies = request.cookies
            session_cookie_id = cookies.get(SESSION_COOKIE_NAME)
            logger.debug(f"[/auth/me] Checking for session cookie '{SESSION_COOKIE_NAME}'. Found: {'Yes' if session_cookie_id else 'No'}")
            if session_cookie_id: auth_method = "Cookie"

            if session_cookie_id:
                # try anidado solo para la lógica específica de la cookie
                try:
                    # Abrir conexión SOLO si no se abrió antes o se cerró (aunque no deberíamos cerrarla aquí)
                    if conn is None: # Solo abrir si no existe del bloque Bearer
                         conn = get_db_connection()
                         if not conn: raise HTTPException(status_code=503, detail="Database unavailable")

                    result = conn.execute("""
                        SELECT provider, user_provider_id, access_token, refresh_token,
                               token_type, expires_at, user_info
                        FROM user_sessions
                        WHERE session_cookie_id = ?
                    """, (session_cookie_id,)).fetchone()

                    if not result:
                        logger.warning(f"[/auth/me] Session cookie ID '{session_cookie_id}' found but no matching session in DB.")
                        response_content = {"authenticated": False, "reason": "Session not found in DB"}
                        response = Response(content=json.dumps(response_content), media_type="application/json", status_code=200)
                        response.delete_cookie(SESSION_COOKIE_NAME, path="/", domain="localhost")
                        # NO cerrar conexión aquí, lo hará el finally
                        return response # Retornar directamente

                    provider, user_pid, access_token, refresh_token, t_type, expires_at_db, user_info_json = result

                    # --- CORRECCIÓN DATETIME (como antes) ---
                    token_expired = False
                    if expires_at_db:
                        if isinstance(expires_at_db, datetime) and expires_at_db.tzinfo is None:
                            expires_at_aware = expires_at_db.replace(tzinfo=timezone.utc)
                        elif isinstance(expires_at_db, datetime):
                             expires_at_aware = expires_at_db
                        else: expires_at_aware = None

                        if expires_at_aware and datetime.now(timezone.utc) > expires_at_aware:
                            token_expired = True
                            logger.warning(f"[/auth/me] Session {session_cookie_id} found via cookie but token expired.")
                    # --- FIN CORRECCIÓN DATETIME ---

                    if token_expired:
                        response_content = {"authenticated": False, "reason": "Token expired"}
                        response = Response(content=json.dumps(response_content), media_type="application/json", status_code=200)
                        # NO cerrar conexión aquí
                        return response # Retornar directamente

                    # Sesión válida vía cookie y token no expirado
                    conn.execute("UPDATE user_sessions SET last_accessed_at = current_timestamp WHERE session_cookie_id = ?", (session_cookie_id,))
                    user_info = json.loads(user_info_json) if user_info_json else {}
                    session_data = { # ... (datos de sesión como antes) ...
                        "authenticated": True, "provider": provider, "user_info": user_info,
                        "token_data": {
                            "access_token": access_token, "refresh_token": refresh_token, "token_type": t_type,
                            "expires_at": expires_at_db.isoformat() if isinstance(expires_at_db, datetime) else expires_at_db
                        }
                    }
                    logger.info(f"[/auth/me] Session validated via Cookie for {provider} user {user_pid}")

                except Exception as e:
                    logger.exception(f"[/auth/me] Error checking cookie session {session_cookie_id}: {e}")
                    # No retornar aquí necesariamente, dejar que el finally cierre y luego devolver no autenticado
                    # Considerar si este error debe devolver 500 o simplemente auth false
                    session_data = None # Asegurar que no se devuelva data si hubo error aquí


        # 3. Devolver resultado (después del bloque try principal)
        if session_data:
            logger.debug(f"[/auth/me] Returning authenticated session data (validated via {auth_method}).")
            return session_data
        else:
            reason = "No valid session found"
            if auth_method == "Bearer": reason = "Bearer token invalid/expired or session expired"
            elif auth_method == "Cookie": reason = "Cookie invalid or session expired"
            logger.debug(f"[/auth/me] Returning not authenticated (method attempted: {auth_method}). Reason: {reason}")
            return {"authenticated": False, "reason": reason}

    finally: # Este bloque se ejecuta siempre, después del try o si ocurre una excepción no capturada o return
        if conn: # Comprobar solo si la conexión se llegó a asignar
            conn.close()
            logger.debug("[/auth/me] DB connection closed in finally block.")


@app.get("/auth/logout") # Cambiado a GET para que sea fácil redirigir desde link_button
async def logout_user(request: Request):
    """Borra la sesión de la BD, elimina la cookie y redirige a Streamlit."""
    session_cookie_id = request.cookies.get(SESSION_COOKIE_NAME)
    logger.info(f"Logout requested. Session cookie ID found: {bool(session_cookie_id)}")

    if session_cookie_id:
        conn = None
        try:
            conn = get_db_connection()
            if conn:
                conn.execute("DELETE FROM user_sessions WHERE session_cookie_id = ?", [session_cookie_id])
                logger.info(f"Session deleted from DB for cookie ID: {session_cookie_id}")
        except Exception as e:
            logger.error(f"Error deleting session from DB during logout: {e}", exc_info=True)
        finally:
             if conn: conn.close()

    # Crear respuesta de redirección para borrar la cookie
    response = RedirectResponse(url=BASE_URL, status_code=307) # Redirige de vuelta a Streamlit
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        domain="localhost" # TODO: Production domain
    )
    logger.debug(f"Session cookie '{SESSION_COOKIE_NAME}' deletion requested via Set-Cookie.")
    return response


# --- Privacy Policy y Root (sin cambios) ---
@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    # ... (sin cambios) ...
    html_content = """..."""
    return HTMLResponse(content=html_content)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed.")
    return {"message": "AIPost Backend API"}

# --- Include Routers ---
try:
    # Asegúrate que los routers estén definidos y listos para ser incluidos
    app.include_router(content_router, dependencies=[Depends(get_current_session_data_from_token)]) # Aplicar dependencia globalmente si aplica
    app.include_router(analytics_router, dependencies=[Depends(get_current_session_data_from_token)])# Aplicar dependencia globalmente si aplica
    logger.info("✅ Routers included correctly with auth dependency")
except NameError as e:
     logger.error(f"❌ Error including routers: Router variable not defined? {e}", exc_info=True)
     # Decide si quieres lanzar el error o continuar sin los routers
     # raise e
except Exception as e:
    logger.error(f"❌ Error including routers: {str(e)}", exc_info=True)
    raise e