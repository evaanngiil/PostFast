from langchain_core.prompts import ChatPromptTemplate
from src.agents.content_agent.agent_state import InternalState
from src.core.constants import PRO_LLM
from src.agents.content_agent.callbacks import get_token_callback
from langchain_core.runnables import RunnableConfig

async def refine_for_engagement(state: InternalState, config: RunnableConfig) -> InternalState:
    print("--- Refinando para Máxima Interacción ---")
    print(f"[DEBUG] Nodo refine_for_engagement - Estado de entrada: {state}")

    print(f"REVISION CYCLE: {state.get('revision_cycles')}")
    node_name = "refine_for_engagement"
    current_cycles = state.get("revision_cycles", 0)

    if current_cycles is None:
        current_cycles = 0

    revision_cycles = current_cycles + 1
    state['revision_cycles'] = revision_cycles
    print(f"--- Ciclo de revisión #{state['revision_cycles']} ---")

    if state.get("refined_content") and revision_cycles > 1:
        print(f"Usando contenido refinado de la revisión anterior. Revisión #{revision_cycles}")
        content_to_refine = state["refined_content"]
    else:
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

    refined = await chain.ainvoke({
        "human_feedback": state.get("human_feedback", "N/A. Mejora el engagement general."),
        "review_notes": state.get("review_notes", "N/A"),
        "refined_content": content_to_refine
    }, config=config)
    
    state['refined_content'] = str(refined.content)
    
    print(f"[DEBUG] Nodo refine_for_engagement - Estado del feedback: {state.get("human_feedback")}")

    state['human_feedback'] = None

    return state