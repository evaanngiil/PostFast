import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

LI_CLIENT_ID = os.getenv("LI_CLIENT_ID")
LI_CLIENT_SECRET = os.getenv("LI_CLIENT_SECRET")

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
# LI_API_URL = "https://api.linkedin.com/rest"
LI_API_URL = "https://api.linkedin.com/v2"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("CRITICAL: DATABASE_URL environment variable not set.")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Lazy import to avoid circular import
def get_pro_llm():
    from src.agents.utils.llm_factory import LLMFactory
    return LLMFactory.get_llm(llm_name="gemini-2.0-flash")

def get_flash_llm():
    from src.agents.utils.llm_factory import LLMFactory
    return LLMFactory.get_llm(llm_name="gemini-2.0-flash-lite")

PRO_LLM = get_pro_llm()
FLASH_LLM = get_flash_llm()