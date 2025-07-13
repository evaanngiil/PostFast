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

async def refine_for_engagement(state: InternalState, config: RunnableConfig) -> InternalState:
    print("--- Refinando para Máxima Interacción ---")
    
    # Solo mostrar el valor actual de revision_cycles, no inicializar
    print(f"REVISION CYCLE: {state.get('revision_cycles')}")

    node_name = "refine_for_engagement"
    
    # Incrementar revision_cycles al entrar en este nodo (porque vamos a refinar)
    current_cycles = state.get("revision_cycles", 0)
    if current_cycles is None:
        current_cycles = 0
    
    revision_cycles = current_cycles + 1
    state['revision_cycles'] = revision_cycles
    
    print(f"--- Ciclo de revisión #{state['revision_cycles']} ---")
    
    # Determinar sobre qué texto trabajar
    if state.get("refined_content") and revision_cycles > 1:
        # Si ya estamos en un ciclo de revisión > 1, mejoramos el último contenido refinado
        print(f"Usando contenido refinado de la revisión anterior. Revisión #{revision_cycles}")
        content_to_refine = state["refined_content"]
    else:
        # Si es la primera vez, partimos del borrador original
        print("Usando borrador original para la primera revisión.")
        content_to_refine = state["draft_content"]

    prompt = ChatPromptTemplate.from_template(
        """Eres un especialista en engagement. Tu tarea principal es aplicar las correcciones solicitadas por el usuario.
            Si no hay feedback del usuario, aplica las notas de la IA.
            Mejora el borrador para maximizar las interacciones.
            
            **Feedback del Usuario (MÁXIMA PRIORIDAD):**
            {human_feedback}

            **Notas de la IA (si no hay feedback del usuario):**
            {review_notes}

            **Texto a Mejorar:**
            {refined_content}

            Tu respuesta DEBE ser únicamente el borrador refinado.
            Borrador Refinado:"""
    )

    if (token_callback := get_token_callback(config)):
        token_callback.set_current_node(node_name)

    chain = prompt | PRO_LLM
    
    # Invocamos la cadena con el texto correcto
    refined = await chain.ainvoke({
        "human_feedback": state.get("human_feedback", "N/A"),
        "review_notes": state.get("review_notes", "N/A"),
        "refined_content": content_to_refine
    }, config=config)
    
    # La salida siempre actualiza 'refined_content' para el siguiente ciclo
    state['refined_content'] = refined.content
    
    return state