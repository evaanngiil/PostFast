from langchain_core.prompts import ChatPromptTemplate
from src.agents.content_agent.agent_state import InternalState
from src.core.logger import logger
from src.core.constants import FLASH_LLM, GENAI_API_KEY
from langchain_core.runnables import RunnableConfig
from src.agents.content_agent.callbacks import get_token_callback
from langchain_google_genai import ChatGoogleGenerativeAI

FLASH_LLM  = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    api_key=GENAI_API_KEY,
    temperature=0.9
)

async def extract_final_post(state: InternalState, config: RunnableConfig) -> InternalState:
    print("--- Extrayendo Contenido Limpio del Post ---")
    
    # Solo mostrar el valor actual de revision_cycles, no inicializar
    print(f"REVISION CYCLE: {state.get('revision_cycles')}")
    
    node_name = "extract_final_post"
    prompt = ChatPromptTemplate.from_template(
        """Analiza el siguiente texto. Contiene un post para una red social, pero puede incluir texto introductorio no deseado.
        Tu única tarea es identificar y extraer el contenido del post social, desde la primera palabra hasta el último hashtag, sin incluir nada más.
        Si el texto ya parece ser solo el post, simplemente devuélvelo tal cual.

        Texto a Limpiar:
        ---
        {formatted_output}
        ---

        Post Limpio Extraído:"""
    )

    if (token_callback := get_token_callback(config)):
        token_callback.set_current_node(node_name)

    chain = prompt | FLASH_LLM
    
    # Pasar solo los campos necesarios al LLM
    clean_post = await chain.ainvoke({
        "formatted_output": state.get("formatted_output", "")
    }, config=config)
    
    state['final_post'] = clean_post.content # Sobrescribir final_post con la versión limpia

    return state