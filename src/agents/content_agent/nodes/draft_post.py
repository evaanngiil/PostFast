from langchain_core.prompts import ChatPromptTemplate
from src.agents.content_agent.agent_state import InternalState
from src.core.logger import logger
from src.core.constants import PRO_LLM, GENAI_API_KEY
from src.agents.content_agent.callbacks import get_token_callback
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

PRO_LLM  = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    api_key=GENAI_API_KEY,
    temperature=0.9
)

async def draft_post(state: InternalState, config: RunnableConfig) -> InternalState:
    print("--- Escribiendo Borrador Inicial ---")
    
    # Solo mostrar el valor actual de revision_cycles, no inicializar
    print(f"REVISION CYCLE: {state.get('revision_cycles')}")

    node_name = "draft_post"
    prompt = ChatPromptTemplate.from_template(
        """Eres un redactor creativo experto en LinkedIn. Usando el siguiente briefing, escribe un borrador atractivo y de alta calidad.
        Concéntrate en un gancho potente y desarrollo claro. Tu respuesta DEBE ser únicamente el borrador.

        Briefing:
        {creative_brief}

        Borrador del Post:"""
    )

    if (token_callback := get_token_callback(config)):
        token_callback.set_current_node(node_name)

    chain = prompt | PRO_LLM
    
    # Pasar solo los campos necesarios al LLM
    draft = await chain.ainvoke({
        "creative_brief": state.get("creative_brief", "")
    }, config=config)
    
    state['draft_content'] = draft.content

    return state