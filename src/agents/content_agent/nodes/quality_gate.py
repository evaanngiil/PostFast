from langchain.prompts.chat import ChatPromptTemplate
from src.agents.content_agent.agent_state import InternalState
from src.core.logger import logger
from src.core.constants import FLASH_LLM, GENAI_API_KEY
from langchain_core.runnables import RunnableConfig
from src.agents.content_agent.callbacks import get_token_callback
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.constants import END

from typing import Union

FLASH_LLM  = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    api_key=GENAI_API_KEY,
    temperature=0.9
)

async def quality_gate(state: InternalState, config: RunnableConfig) -> Union[InternalState, str]:
    print("--- Realizando Control de Calidad ---")
    
    print(f"REVISION CYCLE: {state.get('revision_cycles')}")

    node_name = "quality_gate"

    # Verificar si hemos alcanzado el máximo de revisiones
    current_cycles = state.get("revision_cycles", 0)
    if current_cycles is None:
        current_cycles = 0
    
    if current_cycles > 2:
        print("--- Máximo de revisiones alcanzado. Aprobando. ---")
        return "end"

    prompt = ChatPromptTemplate.from_template(
        """Eres un director de marketing muy exigente. Evalúa el siguiente post para LinkedIn basado en el briefing original.
        ¿El post es atractivo, asertivo y cumple con todos los objetivos?
        Responde SOLAMENTE con una de las siguientes opciones:
        - "APROBADO" si el post es excelente y está listo para publicar.
        - "REQUIERE MEJORA: [Describe brevemente qué falta. Por ejemplo: 'El CTA no es claro' o 'El tono es demasiado formal']" si necesita cambios.

        Briefing Original:
        {creative_brief}
        Post Final Propuesto:
        {final_post}

        Tu Veredicto:"""
    )

    if (token_callback := get_token_callback(config)):
        token_callback.set_current_node(node_name)

    chain = prompt | FLASH_LLM
    
    # Pasar solo los campos necesarios al LLM
    response = await chain.ainvoke({
        "creative_brief": state.get("creative_brief", ""),
        "final_post": state.get("final_post", "")
    }, config=config)

    verdict_text = response.content.upper() # Convertir a mayúsculas para ser insensible al caso
    
    # ========= LÓGICA DE DECISIÓN ROBUSTA =========
    # Buscamos la palabra clave APROBADO al inicio del texto.
    # Esto evita falsos positivos si "APROBADO" aparece en las notas de mejora.
    if verdict_text.strip().startswith("APROBADO"):
        print(f"--- Veredicto: APROBADO. Finalizando ciclo. ---")
        state['review_notes'] = "Aprobado en el control de calidad."
        return "end"
    else:
        # Cualquier otra cosa se considera como que requiere mejora.
        print(f"--- Veredicto: REQUIERE MEJORA. Notas: {response.content} ---")
        # Guardamos las notas para el siguiente ciclo de refinamiento
        state['review_notes'] = response.content 
        return "refine"