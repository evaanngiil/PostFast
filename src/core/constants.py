import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

FB_CLIENT_ID = os.getenv("FB_CLIENT_ID")
FB_CLIENT_SECRET = os.getenv("FB_CLIENT_SECRET")
LI_CLIENT_ID = os.getenv("LI_CLIENT_ID")
LI_CLIENT_SECRET = os.getenv("LI_CLIENT_SECRET")

BASE_URL = os.getenv("BASE_URL")
FASTAPI_URL = os.getenv("FASTAPI_URL")

FB_REDIRECT_URI = f"{FASTAPI_URL}/auth/callback/facebook"
LI_REDIRECT_URI = f"{FASTAPI_URL}/auth/callback/linkedin"
X_REDIRECT_URI = f"{FASTAPI_URL}/auth/callback/x"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

SECRET_KEY = os.getenv("SECRET_KEY")

# API Constants 
FB_GRAPH_URL = "https://graph.facebook.com/v18.0"
# LI_API_URL = "https://api.linkedin.com/rest"
LI_API_URL = "https://api.linkedin.com/v2"
