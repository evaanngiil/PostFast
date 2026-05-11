import os
from dotenv import load_dotenv

# Carga inicial de variables de entorno (dotenv).
load_dotenv()

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

LI_CLIENT_ID = os.getenv("LI_CLIENT_ID")
LI_CLIENT_SECRET = os.getenv("LI_CLIENT_SECRET")
LI_SCOPES = [
        'rw_organization_admin',
        'w_member_social',
        'r_basicprofile',
        'r_organization_admin',
        'email',
        'openid',
        'r_liteprofile',
        'r_organization_social',
        'w_organization_social',
        'r_marketing_leadgen_automation',
        'rw_ads',
        'r_ads',
        'r_ads_reporting',
        'r_1st_connections_size',
        'r_events',
        'r_ads_leadgen_automation'
    ]


BASE_URL = os.getenv("BASE_URL")
if not BASE_URL:
    BASE_URL = "http://localhost:8501"
    print("WARNING: BASE_URL not set in environment. Defaulting to http://localhost:8501 (dev only).")

FASTAPI_URL = os.getenv("FASTAPI_URL")
if not FASTAPI_URL:
    FASTAPI_URL = "http://localhost:8000"
    print("WARNING: FASTAPI_URL not set in environment. Defaulting to http://localhost:8000 (dev only).")

LI_REDIRECT_URI = f"{FASTAPI_URL}/auth/callback/linkedin"
X_REDIRECT_URI = f"{FASTAPI_URL}/auth/callback/x"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

SECRET_KEY = os.getenv("SECRET_KEY")

# Constantes de integración con APIs externas (LinkedIn).
LI_API_URL = "https://api.linkedin.com/v2"
LI_API_URL_REST = "https://api.linkedin.com/rest"

# Configuración de base de datos y auth (Supabase).
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_CONN_STRING = os.getenv("SUPABASE_CONN_STRING")

# Configuración de caché / message broker (Redis).
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"


# Límites diarios del free-tier (RPD):
#   gemini-2.5-flash         20 RPD  
#   gemini-2.5-flash-lite    20 RPD 
#   gemini-3-flash           20 RPD 
#   gemini-3.1-flash-lite-preview   500 RPD
#   gemini-2.5-pro            0 RPD  

# Helpers de importación diferida (lazy load) para compatibilidad con LLMFactory.
def get_smart_llm(name: str = "gemini-2.5-flash"):
    """
    Instancia el LLM configurado para tareas complejas vía lazy import.

    :param name: Nombre del modelo LLM a inicializar.
    :returns: Objeto del modelo instanciado.
    """
    from src.agents.utils.llm_factory import LLMFactory
    return LLMFactory.get_llm(llm_name=name)

def get_fast_llm(name: str = "gemini-3.1-flash-lite-preview"):
    """
    Instancia el LLM configurado para tareas rápidas y triviales vía lazy import.

    :param name: Nombre del modelo LLM a inicializar.
    :returns: Objeto del modelo instanciado.
    """
    from src.agents.utils.llm_factory import LLMFactory
    return LLMFactory.get_llm(llm_name=name)

# Modelo designado para tareas creativas o de razonamiento complejo (ej. redacción de posts).
SMART_LLM = "gemini-flash-latest"

# Modelo designado para tareas deterministas o de alta frecuencia (ej. parsers, formato JSON).
MEDIUM_LLM = "gemini-3.1-flash-lite-preview"

# Modelo designado para procesamiento batch de análisis de posts.
ANALYSIS_LLM = "gemini-3.1-flash-lite-preview"

# Modelo designado para tareas de complejidad media (ej. web scraping, brainstroming).
FAST_LLM = "gemini-3.1-flash-lite-preview"


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")