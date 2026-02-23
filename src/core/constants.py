import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

# LI_CLIENT_ID = os.getenv("LI_CLIENT_ID")
# LI_CLIENT_SECRET = os.getenv("LI_CLIENT_SECRET")
# LI_SCOPES =  [
#         'r_member_postAnalytics',
#         'r_organization_followers',
#         'r_organization_social',
#         'rw_organization_admin',
#         'r_organization_social_feed',
#         'w_member_social',
#         'w_organization_social',
#         'r_basicprofile',
#         'w_organization_social_feed',
#         'w_member_social_feed',
#         'r_1st_connections_size'
#     ]

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
    # Default to local Streamlit dev server when not configured
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

# API Constants 
LI_API_URL = "https://api.linkedin.com/v2"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("CRITICAL: DATABASE_URL environment variable not set.")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"


# Lazy import to avoid circular import
def get_smart_llm(name: str = "gemini-2.0-flash"):
    from src.agents.utils.llm_factory import LLMFactory
    return LLMFactory.get_llm(llm_name=name)

def get_fast_llm(name: str = "gemini-2.0-flash-lite"):
    from src.agents.utils.llm_factory import LLMFactory
    return LLMFactory.get_llm(llm_name=name)

# SMART_LLM = get_smart_llm(name="gemini-2.5-flash-lite")
# FAST_LLM = get_fast_llm(name="gemini-2.0-flash")

SMART_LLM = "gemini-2.5-flash-lite"
FAST_LLM = "gemini-2.0-flash"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")