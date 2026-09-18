"""
Nodo Idea Expander para PostFast.
Toma la idea cruda del usuario y la expande en un concepto estratégico,
incorporando contexto semántico de la empresa (recuperado vía RAG) y
respetando el historial de duplicados para no proponer ideas redundantes.
"""
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Dict, Any

from src.agents.multi_agent.state import AgentState, PostIdea
from src.agents.multi_agent.utils import slim_company_profile
from src.services.rag_service import search_knowledge
from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
from src.core.logger import logger


class KnowledgeGapAssessment(BaseModel):
    """Veredicto sobre si el conocimiento verificado sustenta la petición del usuario."""
    has_gap: bool = Field(
        description="True SOLO si la petición exige un hecho concreto (una relación/alianza con un tercero, "
                    "una cifra, un caso, un producto/servicio con nombre, un hito) que NO está respaldado por "
                    "el conocimiento corporativo provisto."
    )
    missing_info: str = Field(
        default="",
        description="Una frase con QUÉ información concreta falta. Vacío si has_gap es False.",
    )
    user_message: str = Field(
        default="",
        description="Aviso breve y accionable para el usuario (máx. 2 frases) en español: qué información "
                    "verificada falta y cómo aportarla (añadir documento/enlace o reformular). Vacío si no hay gap.",
    )


GAP_ASSESSMENT_PROMPT = """Eres un auditor de cobertura de conocimiento para la empresa "{company_name}".

El usuario quiere publicar un post con esta petición:
"{user_idea}"

Este es TODO el conocimiento corporativo VERIFICADO disponible (perfil + base de conocimiento):
--- PERFIL DE LA EMPRESA ---
{company_summary}
--- BASE DE CONOCIMIENTO (RAG) ---
{rag_context}

Decide si ese conocimiento contiene información ESPECÍFICA y SUSTANTIVA para cumplir la petición con datos reales,
o si el post resultaría genérico/especulativo por falta de información.

Marca `has_gap = True` SOLO si la petición exige un HECHO CONCRETO que NO aparece respaldado en el conocimiento.

REGLAS CLAVE:
- Información SOBRE un tercero (p. ej. la web de otra empresa) NO demuestra una relación de "{company_name}" con ese
  tercero. Si la petición pide hablar de "nuestra relación / colaboración / alianza con X" y el conocimiento solo
  describe a X (pero no el vínculo real con "{company_name}"), ES un gap.
- Si la petición es general, de opinión, de liderazgo de pensamiento o divulgativa (no exige hechos concretos de la
  empresa), `has_gap = False`.
- El perfil de empresa (misión, especialidades, "acerca de") cuenta como conocimiento verificado.

Responde en el formato estructurado requerido.
"""


def _assess_knowledge_gap(user_idea: str, company_profile: dict, rag_context: str, llm) -> Dict[str, Any]:
    """
    Evalúa si la base de conocimiento sustenta la petición concreta del usuario.

    Devuelve siempre un dict {has_gap, missing_info, user_message}; ante cualquier
    fallo asume que NO hay gap (fail-open) para no bloquear la generación.
    """
    no_gap = {"has_gap": False, "missing_info": "", "user_message": ""}
    try:
        company_name = (company_profile or {}).get("name", "la empresa")
        company_summary = json.dumps(slim_company_profile(company_profile), ensure_ascii=False)
        chain = (
            ChatPromptTemplate.from_template(GAP_ASSESSMENT_PROMPT)
            | llm.with_structured_output(KnowledgeGapAssessment)
        )
        result = chain.invoke({
            "company_name": company_name,
            "user_idea": user_idea,
            "company_summary": company_summary,
            "rag_context": rag_context or "Sin conocimiento específico indexado.",
        })
        if not result:
            return no_gap
        gap = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        logger.info(
            "Idea Expander [gap]: has_gap=%s | %s",
            gap.get("has_gap"), (gap.get("missing_info") or "")[:120],
        )
        return gap
    except Exception as e:
        logger.warning(f"Idea Expander: fallo evaluando el vacío de conocimiento: {e}")
        return no_gap

PROMPT_TEMPLATE = """
Eres un Director Creativo y Estratega de Contenido en LinkedIn de clase mundial.
Tu tarea es expandir la idea inicial de un usuario en una propuesta de post detallada y con enfoque estratégico,
alineada con la identidad corporativa de la empresa y la voz de la marca.

**Perfil de la Organización:**
{company_profile}

**Guía de Tono de Marca:**
{brand_persona}

**Contexto del Negocio y Productos Encontrados (RAG Context):**
{rag_context}

**Contexto Editorial e Historial (Duplicados a Evitar):**
{duplicate_context}

**Idea Inicial del Usuario:**
"{user_post_idea}"

**Instrucciones:**
1. Analiza el RAG Context para entender cómo se relacionan los productos, servicios o valores de la empresa con la idea del usuario.
2. Revisa el Historial Editorial para asegurarte de que el enfoque de la idea sea diferente de lo ya publicado.
3. Expande la idea definiendo un "topic" claro y refinado, un "suggested_format" adecuado para LinkedIn (ej. carrusel, story, debate, tutorial paso a paso) y un "strategic_goal" (ej. posicionamiento, generación de leads, empleabilidad, engagement).
4. CRÍTICO: el "topic" debe PRESERVAR el propósito literal de la petición del usuario (anunciar, comparar, celebrar, aportar datos...). Enriquecer la idea nunca puede significar cambiar el tipo de post solicitado.

Devuelve EXCLUSIVAMENTE la estructura JSON que representa a `PostIdea`.
"""

def run_idea_expander_node(state: AgentState) -> Dict[str, Any]:
    print("--- 💡 EJECUTANDO EXPANSOR DE IDEAS CON RAG ---")
    logger.info("=== IDEA EXPANDER: start ===")
    
    user_idea = state.get("user_post_idea", "")
    company_profile = state.get("company_profile", {})
    org_urn = company_profile.get("urn", "") if company_profile else ""
    brand_persona = state.get("brand_persona_json", {})
    duplicate_context = state.get("duplicate_context", "Tema nuevo. Sin posts previos similares.")
    
    if not user_idea or not company_profile:
        raise ValueError("Faltan datos base (user_post_idea o company_profile) para la fase de expansión.")
        
    # Consultar el RAG con la idea del usuario para capturar productos o valores aplicables
    rag_results = []
    if org_urn:
        logger.info(f"Buscando contexto en RAG para expandir la idea: '{user_idea}'...")
        rag_results = search_knowledge(
            query=user_idea,
            org_urn=org_urn,
            threshold=0.5,
            limit=4
        )
        
    rag_context = "\n".join(
        f"[{res['source_type']}] {res['content']}" for res in rag_results
    ) if rag_results else "No se encontró información específica en RAG. Procede con el perfil general."

    # Detección de vacío de conocimiento: ¿sustenta el RAG la petición concreta,
    # o el post saldría genérico? Se avisa al usuario en la revisión (HITL).
    gap_llm = ChatGoogleGenerativeAI(
        model=MEDIUM_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=0.0,
    )
    knowledge_gap = _assess_knowledge_gap(user_idea, company_profile, rag_context, gap_llm)
    if knowledge_gap.get("has_gap") and state.get("task_id"):
        try:
            from src.services.realtime_service import broadcast_task_status_sync
            broadcast_task_status_sync(state["task_id"], "RUNNING", {
                "node": "Idea Expander",
                "message": (
                    "⚠️ Aviso: no hay información verificada en tu base de conocimiento sobre "
                    f"{knowledge_gap.get('missing_info') or 'la petición'}. El post será general."
                ),
            })
        except Exception:
            pass

    llm = ChatGoogleGenerativeAI(
        model=MEDIUM_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=0.6
    )
    structured_llm = llm.with_structured_output(PostIdea)
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | structured_llm
    
    try:
        expanded_idea = chain.invoke({
            "company_profile": json.dumps(slim_company_profile(company_profile), ensure_ascii=False),
            "brand_persona": json.dumps(brand_persona, ensure_ascii=False),
            "rag_context": rag_context,
            "duplicate_context": duplicate_context,
            "user_post_idea": user_idea
        })
        
        if hasattr(expanded_idea, "model_dump"):
            expanded_idea_dict = expanded_idea.model_dump()
        elif hasattr(expanded_idea, "dict"):
            expanded_idea_dict = expanded_idea.dict()
        else:
            expanded_idea_dict = dict(expanded_idea)
            
        print("✅ Idea expandida y alineada con RAG y políticas corporativas.")
        logger.info("=== IDEA EXPANDER: completed ===")
        return {"fleshed_out_idea": expanded_idea_dict, "knowledge_gap": knowledge_gap}

    except Exception as e:
        logger.error(f"Error expandiendo la idea del post: {e}")
        # Fallback simple
        fallback = {
            "topic": user_idea,
            "suggested_format": "Post de texto directo con gancho e insights",
            "strategic_goal": "Aumentar visibilidad y posicionamiento experto en el sector"
        }
        return {"fleshed_out_idea": fallback, "knowledge_gap": knowledge_gap}
