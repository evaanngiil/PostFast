from langchain_core.prompts import ChatPromptTemplate
from src.agents.content_agent.agent_state import InternalState
from src.core.logger import logger
from src.core.constants import PRO_LLM, GENAI_API_KEY
from src.agents.content_agent.callbacks import TokenUsageCallback, get_token_callback
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI


PRO_LLM  = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    api_key=GENAI_API_KEY,
    temperature=0.9
)

# Cada nodo recibe y devuelve el InternalState completo
async def analyze_audience(state: InternalState, config: RunnableConfig) -> InternalState:
    print("--- Analizando Audiencia y Creando Briefing ---")
    node_name = "analyze_audience"

    # Inicializar revision_cycles a 0 solo si es None
    if state.get('revision_cycles') is None:
        state['revision_cycles'] = 0
        print(f"⚠️  revision_cycles inicializado a 0 (era None)")
    print(f"REVISION CYCLE: {state.get('revision_cycles')}")
    prompt = ChatPromptTemplate.from_template(
        """Eres un estratega de marketing de contenidos. Tu tarea es crear un 'briefing creativo' para un redactor.
        Basado en la siguiente información, define un ángulo de ataque claro, 3 puntos clave a cubrir y el objetivo principal del post.

        Cuenta: {account_name}
        Nicho/Audiencia: {niche}
        Tono Deseado: {tone}
        Petición del Usuario: {query}
        Link Relevante: {link_url}

        Briefing Creativo:"""
    )

    if (token_callback := get_token_callback(config)):
        token_callback.set_current_node(node_name)

    chain = prompt | PRO_LLM
    
    # Pasar solo los campos necesarios al LLM
    brief = await chain.ainvoke({
        "account_name": state.get("account_name", ""),
        "niche": state.get("niche", ""),
        "tone": state.get("tone", ""),
        "query": state.get("query", ""),
        "link_url": state.get("link_url", "")
    }, config=config)
    
    state['creative_brief'] = brief.content

    return state

    
