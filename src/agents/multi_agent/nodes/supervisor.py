"""
Módulo de enrutamiento determinista para el grafo de LangGraph.

Implementa la lógica de bifurcación condicional basada en validaciones de estado (if/elif).
Garantiza el flujo secuencial estricto a través de las 14 fases de PostFast v2,
incluyendo bucles de corrección automática si el Fact Checker o el Safety Guard fallan.

Soporta además:
- Ruteo al nodo `content_editor` para ediciones dirigidas por feedback humano (HITL)
  y para el modo edición rápida, separando "editar" de "generar".
- Configuración de ablación (`ablation_disabled`) para los estudios comparativos del
  TFG: permite desactivar capacidades individuales sin modificar la topología.
"""

from typing import Union, List
from src.agents.multi_agent.state import AgentState
from src.core.logger import logger


def _is_disabled(state: AgentState, capability: str) -> bool:
    """Indica si una capacidad está desactivada por configuración de ablación."""
    return capability in (state.get("ablation_disabled") or [])


def supervisor_router_logic(state: AgentState) -> Union[str, List[str]]:
    """
    Evalúa la completitud secuencial del payload de AgentState para dictaminar el siguiente nodo activo.

    :param state: Diccionario tipado (AgentState) en su iteración actual.
    :returns: Identificador en string o lista de strings del siguiente(s) worker(s) a disparar.
    """
    logger.info("--- 🔀 SUPERVISOR EVALUANDO ESTADO (14 Fases) ---")

    # ===== FLUJO DE MODO EDICIÓN RÁPIDA =====
    if state.get("edit_mode"):
        logger.info("-> [MODO EDICIÓN RÁPIDA DETECTADO EN SUPERVISOR]")
        if not state.get("draft_post"):
            logger.info("-> content_editor (edición de post pendiente en edición rápida)")
            return "content_editor"
        logger.info("-> human_review (edición rápida completada, saltando validaciones)")
        return "human_review"

    # ===== EDICIÓN DIRIGIDA POR FEEDBACK HUMANO (HITL) =====
    # Tras la revisión humana con feedback, human_review limpia draft_post y
    # conserva last_draft_content: el editor aplica los cambios de forma quirúrgica.
    if (
        state.get("user_feedback")
        and state.get("last_draft_content")
        and not state.get("draft_post")
    ):
        logger.info("-> content_editor (aplicando feedback del usuario sobre el borrador)")
        return "content_editor"

    # ===== FASE 2: ANÁLISIS DE AUDIENCIA Y ENGAGEMENT =====
    if not state.get("engagement_analysis") and not _is_disabled(state, "engagement_analyzer"):
        logger.info("-> engagement_analyzer (análisis de engagement pendiente)")
        return "engagement_analyzer"

    if not state.get("brand_persona_json") and not _is_disabled(state, "persona_analyst"):
        logger.info("-> persona_analyst (perfil de marca pendiente)")
        return "persona_analyst"

    # ===== FASE 3: DETECCIÓN DE DUPLICADOS Y TENDENCIAS =====
    duplicate_pending = (
        state.get("existing_posts_on_topic") is None
        and not _is_disabled(state, "duplicate_detector")
    )
    trends_pending = (
        not state.get("industry_trends")
        and not _is_disabled(state, "trend_researcher")
    )

    if duplicate_pending and trends_pending:
        logger.info("-> duplicate_detector & trend_researcher (ejecutando en paralelo)")
        return ["duplicate_detector", "trend_researcher"]
    elif duplicate_pending:
        logger.info("-> duplicate_detector (búsqueda de duplicados pendiente)")
        return "duplicate_detector"
    elif trends_pending:
        logger.info("-> trend_researcher (investigación de tendencias pendiente)")
        return "trend_researcher"

    # ===== FASE 4: CONCEPTUALIZACIÓN Y CREACIÓN =====
    if not state.get("fleshed_out_idea"):
        logger.info("-> idea_expander (idea expandida pendiente)")
        return "idea_expander"

    if not state.get("draft_post"):
        logger.info("-> content_writer (borrador de post pendiente)")
        return "content_writer"

    # ===== FASE 5: VALIDACIÓN Y COMPLIANCE =====
    if not state.get("fact_check_report") and not _is_disabled(state, "fact_checker"):
        logger.info("-> fact_checker (verificación factual de claims pendiente)")
        return "fact_checker"

    # Bucle de re-ciclo por fallo factual
    fact_report = state.get("fact_check_report") or {}
    if fact_report and not fact_report.get("overall_pass"):
        logger.info("❌ FACT CHECK FALLIDO -> Redirigiendo a content_writer para correcciones")
        return "content_writer"

    if not state.get("safety_report") and not _is_disabled(state, "safety_guard"):
        logger.info("-> safety_guard (auditoría de marca y compliance pendiente)")
        return "safety_guard"

    # Bucle de re-ciclo por fallo en seguridad o políticas
    safety_report = state.get("safety_report") or {}
    if safety_report and not safety_report.get("approved") and safety_report.get("severity") in ("medium", "high", "critical"):
        logger.info("❌ SAFETY GUARD FALLIDO -> Redirigiendo a content_writer para correcciones")
        return "content_writer"

    # ===== FASE FINAL: REVISIÓN HUMANA =====
    logger.info("-> human_review (borrador validado e impecable)")
    return "human_review"


def supervisor_router(state: AgentState) -> dict:
    """Función del nodo (sin operación). La lógica de ruteo vive en la arista condicional."""
    return {}
