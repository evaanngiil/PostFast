"""
Módulo de enrutamiento determinista para el grafo de LangGraph.

Implementa la lógica de bifurcación condicional basada en validaciones de estado (if/elif).
Opera sin inferencia LLM para garantizar latencia cero y ruteo estricto 
en la topología del pipeline (company_profiler -> engagement_extractor -> ... -> human_review).
"""

from src.agents.multi_agent.state import AgentState
from src.core.logger import logger


def supervisor_router_logic(state: AgentState) -> str:
    """
    Evalúa la completitud secuencial del payload de AgentState para dictaminar el siguiente nodo activo.

    :param state: Diccionario tipado (AgentState) en su iteración actual.
    :returns: Identificador en string del siguiente worker a disparar.
    """
    logger.info("--- SUPERVISOR DECIDIENDO (deterministic) ---")

    # 1. El perfil de la empresa debe construirse primero
    if not state.get("company_profile"):
        logger.info("-> company_profiler (perfil de empresa pendiente)")
        return "company_profiler"

    # 2. Extracción de métricas de engagement
    if not state.get("engagement_insights"):
        logger.info("-> engagement_extractor (metricas de engagement pendientes)")
        return "engagement_extractor"

    # 3. Análisis predictivo de los patrones de engagement
    if not state.get("engagement_analysis"):
        logger.info("-> engagement_analyzer (analisis de engagement pendiente)")
        return "engagement_analyzer"

    # 4. El perfil de marca necesita perfil de empresa + datos de engagement
    if not state.get("brand_persona_json"):
        logger.info("-> persona_analyst (perfil de marca pendiente)")
        return "persona_analyst"

    # 5. Expandir la idea del usuario en un brief completo
    if not state.get("fleshed_out_idea"):
        logger.info("-> idea_expander (idea expandida pendiente)")
        return "idea_expander"

    # 6. Escribir el borrador del post
    if not state.get("draft_post"):
        logger.info("-> content_writer (borrador pendiente)")
        return "content_writer"

    # 7. Todo listo -- ir a revision humana
    logger.info("-> human_review (borrador listo)")
    return "human_review"


def supervisor_router(state: AgentState) -> dict:
    """Funcion del nodo (sin operacion). La logica de ruteo vive en la arista condicional."""
    return {}
