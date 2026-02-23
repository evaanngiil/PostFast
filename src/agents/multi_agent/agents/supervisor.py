from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal

from state import AgentState
from src.core.constants import FAST_LLM, GENAI_API_KEY

class Route(BaseModel):
    next_agent: Literal[
        "Company Profiler",
        "Persona Analyst", 
        "Idea Expander", 
        "Content Writer", 
        "FINISH"
    ]

PROMPT_TEMPLATE = """
Eres el Supervisor de un equipo de IA. Tu única función es enrutar al siguiente agente basándote en el estado actual.

**Estado Actual:**
{state_summary}

¿Qué agente debe actuar a continuación?
- `Persona Analyst`: Si ya hay un perfil de empresa (`company_profile`) pero no un perfil de marca (`brand_persona_json`).
- `Idea Expander`: Si ya hay un perfil de marca pero no una idea expandida (`fleshed_out_idea`).
- `Content Writer`: Si ya hay una idea expandida pero no un borrador (`draft_post`).
- `FINISH`: Si el borrador ya está creado.
"""

def create_state_summary(state: AgentState) -> str:
    # Simplificado para el nuevo flujo
    return f"""
- Cuenta Seleccionada: {'Sí, ' + state['selected_account'].get('name') if state.get('selected_account') else 'No'}
- Perfil de Empresa Creado: {'Sí' if state.get('company_profile') else 'No'}
- Perfil de Marca Creado: {'Sí' if state.get('brand_persona_json') else 'No'}
- Idea Expandida Creada: {'Sí' if state.get('fleshed_out_idea') else 'No'}
- Borrador Creado: {'Sí' if state.get('draft_post') else 'No'}
"""

def supervisor_router_logic(state: AgentState) -> str:
    """
    Esta es la función para la ARISTA CONDICIONAL.
    Contiene toda la lógica y devuelve el nombre del siguiente nodo.
    """
    print("--- 👑 SUPERVISOR DECIDIENDO ---")
    
    llm = ChatGoogleGenerativeAI(model=FAST_LLM, google_api_key=GENAI_API_KEY, temperature=0)
    structured_llm = llm.with_structured_output(Route)
    chain = ChatPromptTemplate.from_template(PROMPT_TEMPLATE) | structured_llm
    
    route = chain.invoke({"state_summary": create_state_summary(state)})
    
    print(f"Próxima parada: {route.next_agent}")
    
    node_mapping = {
        "Persona Analyst": "persona_analyst",
        "Idea Expander": "idea_expander",
        "Content Writer": "content_writer",
        "FINISH": "__end__"
    }
    return node_mapping.get(route.next_agent, "__end__")

def supervisor_router(state: AgentState) -> dict:
    """
    Esta es la función para el NODO.
    No necesita hacer nada, ya que la lógica está en la arista.
    Simplemente devuelve un diccionario vacío.
    """
    # No es necesario imprimir nada aquí, la lógica de la arista lo hará.
    return {}
