from src.agents.content_agent.agent_state import InternalState
from src.core.constants import PRO_LLM, GENAI_API_KEY
from src.core.logger import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.errors import NodeInterrupt

PRO_LLM  = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    api_key=GENAI_API_KEY,
    temperature=0.9
)

def human_review_gate(state: InternalState) -> str:
    print("--- Realizando Control de Calidad Humano ---")
    print(f"[DEBUG] Nodo human_review_gate - Estado de entrada: {state}")
    feedback = state.get("human_feedback", "")
    if feedback is None or feedback == "":
        print("--- Esperando feedback humano. Interrumpiendo workflow. ---")
        print(f"[DEBUG] Nodo human_review_gate interrumpe el grafo esperando feedback humano")
        raise NodeInterrupt("Workflow paused for human review")
    feedback = feedback.strip().lower()
    if feedback == "aprobar":
        print("--- Feedback Humano: APROBADO. Finalizando. ---")
        print(f"[DEBUG] Nodo human_review_gate retorna: 'end'")
        return "end"
    else:
        print("--- Feedback Humano: REQUIERE MEJORA. Continuando ciclo. ---")
        print(f"[DEBUG] Nodo human_review_gate retorna: 'refine'")
        return "refine"