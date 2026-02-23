import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any

from state import AgentState, PostIdea
from src.core.constants import SMART_LLM, GENAI_API_KEY

PROMPT_TEMPLATE = """
Eres un Estratega de Contenidos experto. Tu tarea es expandir la idea de un usuario en un concepto de publicación estructurado y estratégico, usando el contexto de la empresa y su voz.

**Perfil de Marca:**
{brand_persona}

**Perfil de la Empresa:**
{company_profile}

**Idea del Usuario:**
"{user_post_idea}"

Expande la idea en un formato JSON `PostIdea` con `topic`, `suggested_format` y `strategic_goal`.
"""

def run_idea_expander_node(state: AgentState) -> Dict[str, Any]:
    print("--- 💡 EJECUTANDO EXPANSOR DE IDEAS ---")
    
    args = {
        "brand_persona": state.get("brand_persona_json"),
        "company_profile": state.get("company_profile"),
        "user_post_idea": state.get("user_post_idea")
    }
    if not all(args.values()):
        raise ValueError("Faltan datos necesarios para expandir la idea.")

    llm = ChatGoogleGenerativeAI(model=SMART_LLM, google_api_key=GENAI_API_KEY, temperature=0.7)
    structured_llm = llm.with_structured_output(PostIdea)
    
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | structured_llm
    
    expanded_idea_object = chain.invoke({k: json.dumps(v) if isinstance(v, dict) else v for k, v in args.items()})
    
    print("✅ Idea expandida y estructurada.")
    print(expanded_idea_object)
    
    # Convertir SIEMPRE a diccionario antes de devolver.
    return {"fleshed_out_idea": expanded_idea_object}
