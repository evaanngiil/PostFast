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

async def finalize_and_format(state: InternalState, config: RunnableConfig) -> InternalState:
    print("--- Finalizando y Optimizando Formato ---")
    
    # Solo mostrar el valor actual de revision_cycles, no inicializar
    print(f"REVISION CYCLE: {state.get('revision_cycles')}")
    
    node_name = "finalize_and_format"
    
    # Instrucción clave añadida
    prompt = ChatPromptTemplate.from_template(
        """Eres un editor de contenidos. Pule el siguiente texto para su publicación en LinkedIn.
        1. Corrige gramática y estilo.
        2. Añade 2-3 emojis relevantes.
        3. Genera 3-5 hashtags estratégicos al final.
        4. Asegura un formato limpio con párrafos cortos.

        Texto a Finalizar:
        {refined_content}
        
        IMPORTANTE: Tu respuesta debe ser ÚNICAMENTE el post finalizado, sin preámbulos como "Aquí tienes el post:".

        Post Finalizado:"""
    )

    if (token_callback := get_token_callback(config)):
        token_callback.set_current_node(node_name)

    chain = prompt | FLASH_LLM
    
    # Pasar solo los campos necesarios al LLM
    formatted_output = await chain.ainvoke({
        "refined_content": state.get("refined_content", "")
    }, config=config)
    
    state['formatted_output'] = formatted_output.content

    return state