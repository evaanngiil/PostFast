import json
import uuid
import base64
from urllib.parse import quote_plus
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from fastapi import FastAPI, Request, HTTPException, Depends, Response, Header
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from requests_oauthlib import OAuth2Session

# --- Core Imports ---
from src.core.constants import (
    SECRET_KEY, LI_CLIENT_ID, LI_REDIRECT_URI, BASE_URL, LI_CLIENT_SECRET, LI_SCOPES
)
from src.core.lifespan import lifespan
from src.core.logger import logger
from src.services.supabase_client import get_supabase
from src.social_apis import get_linkedin_user_info
from src.supabase_auth import get_user_from_supabase_token
from src.dependencies.auth import get_current_session_data_from_token

# --- Router Imports ---
try:
    from src.routers.content import content_router
    ROUTERS_LOADED = True
except ImportError as e:
    logger.warning(f"No se pudieron importar los routers: {e}")
    content_router = None
    ROUTERS_LOADED = False

# --- App Setup ---
app = FastAPI(title="AIPost API", lifespan=lifespan)
SESSION_COOKIE_NAME = "aipost_session_id"

# --- Middleware Setup ---
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helper Functions ---

async def _store_session_in_db(session_data: Dict) -> None:
    """
    Función auxiliar para guardar o actualizar una sesión en Supabase.
    Abstrae la lógica de la base de datos.
    """
    try:
        supabase = get_supabase()
        supabase.table("user_sessions").upsert(
            session_data, on_conflict="user_provider_id,provider"
        ).execute()
        logger.info(f"Sesión guardada para el usuario {session_data.get('user_provider_id')} del proveedor {session_data.get('provider')}")
    except Exception as e:
        logger.exception(f"Error al guardar la sesión en Supabase: {e}")
        raise HTTPException(status_code=500, detail="No se pudo guardar la sesión en la base de datos.")

def _build_streamlit_redirect_url(provider: str, token: str, user_info: Dict, create_session_flag: Optional[str]) -> str:
    """Construye la URL de redirección a Streamlit con los parámetros codificados."""
    user_info_b64 = base64.urlsafe_b64encode(json.dumps(user_info).encode()).decode().rstrip("=")
    token_encoded = quote_plus(token)
    
    url = f"{BASE_URL}?auth_provider={provider}&auth_token={token_encoded}&user_info={user_info_b64}"
    if create_session_flag:
        url += f"&create_platform_session={create_session_flag}"
    return url

# --- Auth Endpoints ---

@app.get("/auth/login/linkedin")
async def linkedin_login(request: Request, create_platform_session: Optional[str] = None):
    """Inicia el flujo de autenticación Oauth2 con LinkedIn."""
    scope =  LI_SCOPES

    oauth = OAuth2Session(LI_CLIENT_ID, redirect_uri=LI_REDIRECT_URI, scope=scope)
    
    authorization_url, state = oauth.authorization_url("https://www.linkedin.com/oauth/v2/authorization")
    
    request.session['oauth_state'] = state
    if create_platform_session:
        request.session['create_platform_session'] = create_platform_session
        
    logger.info(f"Redirigiendo a LinkedIn para autorización. Scopes: {scope}")
    return RedirectResponse(authorization_url)


@app.get("/auth/callback/linkedin")
async def linkedin_callback(request: Request, code: str, state: str, error: Optional[str] = None):
    """Callback de LinkedIn después de la autorización del usuario."""
    if error:
        logger.error(f"Error en el callback de LinkedIn: {error}")
        return RedirectResponse(f"{BASE_URL}?auth_error=linkedin:{error}")

    stored_state = request.session.pop('oauth_state', None)
    if not stored_state or state != stored_state:
        raise HTTPException(status_code=403, detail="State de CSRF inválido.")

    try:
        # 1. Obtener token de acceso
        oauth = OAuth2Session(LI_CLIENT_ID, redirect_uri=LI_REDIRECT_URI, state=state)
        token_data = oauth.fetch_token(
            "https://www.linkedin.com/oauth/v2/accessToken",
            client_secret=LI_CLIENT_SECRET,
            code=code,
            include_client_id=True
        )
        access_token = token_data['access_token']

        # 2. Obtener información del usuario
        user_info = get_linkedin_user_info(access_token)
        user_provider_id = user_info.get('sub')

        if not user_provider_id:
            raise Exception("No se pudo obtener el 'sub' (ID de usuario) de LinkedIn.")

        # 3. Guardar la sesión en la base de datos
        session_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get('expires_in', 3600))
        
        session_payload = {
            "session_cookie_id": session_id,
            "provider": "linkedin",
            "user_provider_id": user_provider_id,
            "access_token": access_token,
            "refresh_token": token_data.get('refresh_token'),
            "expires_at": expires_at.isoformat(),
            "user_info": user_info,
            "last_accessed_at": datetime.now(timezone.utc).isoformat()
        }
        await _store_session_in_db(session_payload)

        # 4. Redirigir de vuelta a Streamlit
        create_session_flag = request.session.pop('create_platform_session', None)
        redirect_url = _build_streamlit_redirect_url("linkedin", access_token, user_info, create_session_flag)
                
        response = RedirectResponse(redirect_url)
        response.set_cookie(
            key=SESSION_COOKIE_NAME, value=session_id,
            httponly=True, secure=False, samesite="lax", max_age=3600 * 24 * 7
        )
        return response

    except Exception as e:
        logger.exception(f"Error crítico durante el callback de LinkedIn: {e}")
        return RedirectResponse(f"{BASE_URL}?auth_error=linkedin:callback_failed")


@app.post("/auth/session/create_from_supabase")
async def create_session_from_supabase(request: Request):
    """Crea una sesión unificada a partir de un JWT de Supabase."""
    try:
        body = await request.json()
        supabase_jwt = body.get("supabase_jwt")
        if not supabase_jwt:
            raise HTTPException(status_code=400, detail="JWT de Supabase es requerido.")

        user = get_user_from_supabase_token(supabase_jwt)
        if not user:
            raise HTTPException(status_code=401, detail="JWT de Supabase inválido o expirado.")

        session_payload = {
            "session_cookie_id": str(uuid.uuid4()),
            "provider": "supabase",
            "user_provider_id": user.id,
            "access_token": supabase_jwt, # Usamos el JWT de Supabase como token de acceso
            "user_info": user.user_metadata or {"email": user.email, "name": user.user_metadata.get('name', 'Usuario')},
            "last_accessed_at": datetime.now(timezone.utc).isoformat(),
        }
        await _store_session_in_db(session_payload)
        
        return {"session_token": supabase_jwt}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error al crear sesión de Supabase: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor al crear la sesión.")


@app.get("/auth/me", response_model=Dict)
async def get_current_user_session(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Verifica la sesión actual del usuario, priorizando el token Bearer
    y luego la cookie de sesión.

    Ejemplo de petición:
    curl -X GET \
        http://localhost:8000/auth/me \
        -H 'Authorization: Bearer <token>' \
        -H 'Content-Type: application/json'

    Donde <token> es el token Bearer que se encuentra en la cookie de sesión.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        logger.debug("Verificando sesión usando token Bearer.")
        token = authorization.split(" ")[1]
    
    if not token:
        return {"authenticated": False, "reason": "No authentication token provided."}

    try:
        supabase = get_supabase()
        result = supabase.table("user_sessions").select("*").eq("access_token", token).maybe_single().execute().data
        
        if not result:
            return {"authenticated": False, "reason": "Session not found for the given token."}

        # Comprobar si la sesión ha expirado (si tiene fecha de expiración)
        expires_at_str = result.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_at:
                return {"authenticated": False, "reason": "Session token has expired."}

        # Actualizar la última hora de acceso y devolver los datos
        supabase.table("user_sessions").update(
            {"last_accessed_at": datetime.now(timezone.utc).isoformat()}
        ).eq("access_token", token).execute()
        
        logger.debug(f"Sesión verificada para el token proporcionado. Usuario : {result.get('user_info')}")
        return {
            "authenticated": True,
            "provider": result.get('provider'),
            "user_info": result.get('user_info', {}),
            "token_data": {
                "access_token": result.get('access_token'),
                "refresh_token": result.get('refresh_token'),
                "expires_at": result.get('expires_at')
            }
        }
    except Exception as e:
        logger.exception(f"Error al verificar la sesión en /auth/me: {e}")
        raise HTTPException(status_code=500, detail="Error interno al verificar la sesión.")


@app.get("/auth/logout")
async def logout_user(authorization: Optional[str] = Header(None)):
    """Cierra la sesión del usuario eliminando la cookie y la entrada en la BBDD."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ")[1]
        try:
            supabase = get_supabase()
            supabase.table("user_sessions").delete().eq("access_token", token).execute()
            logger.info(f"Sesión eliminada de la BBDD asociada al token.")
        except Exception as e:
            logger.error(f"Error al eliminar la sesión de la BBDD durante el logout: {e}")

    response = Response(status_code=200, content=json.dumps({"message": "Logout successful"}))
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response

# --- Routers & Root ---

@app.get("/")
async def root():
    return {"message": "AIPost Backend API está en funcionamiento!"}

@app.get("/auth/email-confirmed")
async def email_confirmed_redirect():
    """
    Redirige al usuario a la página de Streamlit de confirmación de email
    después de que hagan clic en el enlace de verificación.
    """
    # Construye la URL de la página de Streamlit.
    # El nombre 'Email_Confirmation' viene del nombre del archivo 'Email_Confirmation.py'.
    streamlit_confirmation_url = f"{BASE_URL}/Email_Confirmation"
    logger.info(f"Redirigiendo a la página de confirmación de Streamlit: {streamlit_confirmation_url}")
    return RedirectResponse(streamlit_confirmation_url)

if ROUTERS_LOADED:
    app.include_router(
        content_router,
        prefix="/content",
        dependencies=[Depends(get_current_session_data_from_token)] # Protege todas las rutas de este router
    )
    logger.info("✅ Router de contenido incluido correctamente.")