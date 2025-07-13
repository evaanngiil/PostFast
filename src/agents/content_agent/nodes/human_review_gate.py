from langchain_core.prompts import ChatPromptTemplate
from src.agents.content_agent.agent_state import InternalState
from src.core.constants import PRO_LLM, GENAI_API_KEY
from src.core.logger import logger
from src.agents.content_agent.callbacks import get_token_callback
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

PRO_LLM  = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    api_key=GENAI_API_KEY,
    temperature=0.9
)

def human_review_gate(state: InternalState) -> str:
    """Decide si el proceso termina o necesita otro ciclo de refinamiento basado en el feedback humano."""
    print("--- Realizando Control de Calidad Humano ---")
    feedback = state.get("human_feedback", "").strip().lower()

    if not feedback or feedback == "aprobar":
        print("--- Feedback Humano: APROBADO. Finalizando. ---")
        return "end"
    else:
        print("--- Feedback Humano: REQUIERE MEJORA. Continuando ciclo. ---")
        return "refine"