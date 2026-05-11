"""
Módulo principal que define y compila el StateGraph para el pipeline multi-agente de AIPost.

Construye el workflow de generación de contenido conectando los nodos:
supervisor, company_profiler, engagement_extractor, engagement_analyzer,
persona_analyst, idea_expander, content_writer y human_review.

El supervisor ejecuta el ruteo determinista a través de conditional edges
(supervisor_router_logic) sin llamadas a LLM.

El nodo human_review actúa como un interrupt_before: LangGraph pausa la ejecución
antes de entrar, permitiendo que la tarea de Celery detecte la pausa
mediante state_snapshot.next y devuelva el borrador para la revisión del usuario.
Al reanudarse (aprobar / feedback), el grafo continúa desde human_review.
Si se proporcionó feedback, el draft_post se limpia y el grafo itera de nuevo
a través del supervisor hacia content_writer. Si se aprueba, finaliza (END).

Utiliza un PostgresSaver como checkpointer para garantizar la persistencia
a través de los workers de Celery.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from src.agents.multi_agent.state import AgentState
from src.agents.multi_agent.nodes.supervisor import (
    supervisor_router,
    supervisor_router_logic,
)
from src.agents.multi_agent.nodes.company_profiler import (
    run_company_profiler_node,
)
from src.agents.multi_agent.nodes.engagement_extractor import (
    run_engagement_extractor_node,
)
from src.agents.multi_agent.nodes.engagement_analyzer import (
    run_engagement_analyzer_node,
)
from src.agents.multi_agent.nodes.persona_analyst import (
    run_persona_analyst_node,
)
from src.agents.multi_agent.nodes.idea_expander import (
    run_idea_expander_node,
)
from src.agents.multi_agent.nodes.content_writer import (
    run_content_writer_node,
)
from src.core.constants import SUPABASE_CONN_STRING
from src.core.logger import logger


def human_review_node(state: AgentState) -> dict:
    """
    Gestiona la pausa de revisión humana evaluando el feedback proporcionado por el usuario.

    Si se recibe feedback, limpia el payload del borrador actual para forzar
    su regeneración en el siguiente ciclo. De lo contrario, aprueba el contenido.

    :param state: Estado actual del grafo que contiene los datos del pipeline y el feedback.
    :return: Diccionario con la actualización parcial del estado.
    """
    feedback = state.get("user_feedback")
    if feedback:
        logger.info(
            "--- human_review: feedback received ('%s…'), "
            "clearing draft_post for regeneration ---",
            feedback[:60],
        )
        return {"draft_post": None}

    logger.info("--- human_review: draft approved -> END ---")
    return {}


def _human_review_router(state: AgentState) -> str:
    """
    Determina el siguiente nodo a ejecutar tras la evaluación humana.

    Si el borrador fue eliminado (indicando rechazo o feedback), devuelve el control
    al supervisor. Si se mantiene intacto, finaliza el pipeline.

    :param state: Estado actual del grafo posterior al nodo de revisión.
    :return: String con el identificador del siguiente nodo ('supervisor' o '__end__').
    """
    if not state.get("draft_post"):
        return "supervisor"
    return "__end__"


def build_graph() -> StateGraph:
    """
    Ensambla la topología completa del grafo LangGraph con sus respectivos nodos y edges.

    :return: Instancia de StateGraph no compilada con el workflow definido.
    """
    graph = StateGraph(AgentState)

    graph.add_node("supervisor",            supervisor_router)
    graph.add_node("company_profiler",      run_company_profiler_node)
    graph.add_node("engagement_extractor",  run_engagement_extractor_node)
    graph.add_node("engagement_analyzer",   run_engagement_analyzer_node)
    graph.add_node("persona_analyst",       run_persona_analyst_node)
    graph.add_node("idea_expander",         run_idea_expander_node)
    graph.add_node("content_writer",        run_content_writer_node)
    graph.add_node("human_review",          human_review_node)

    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        supervisor_router_logic,
        {
            "company_profiler":      "company_profiler",
            "engagement_extractor":  "engagement_extractor",
            "engagement_analyzer":   "engagement_analyzer",
            "persona_analyst":       "persona_analyst",
            "idea_expander":         "idea_expander",
            "content_writer":        "content_writer",
            "human_review":          "human_review",
        },
    )

    graph.add_edge("company_profiler",      "supervisor")
    graph.add_edge("engagement_extractor",  "supervisor")
    graph.add_edge("engagement_analyzer",   "supervisor")
    graph.add_edge("persona_analyst",       "supervisor")
    graph.add_edge("idea_expander",         "supervisor")
    graph.add_edge("content_writer",        "supervisor")

    graph.add_conditional_edges(
        "human_review",
        _human_review_router,
        {
            "supervisor": "supervisor",
            "__end__": END,
        },
    )

    return graph


def compile_graph():
    """
    Inicializa el checkpointer de Postgres y compila el StateGraph final.

    Configura un NullConnectionPool para instanciar conexiones efímeras a la base de datos,
    evitando los problemas de PoolTimeout derivados de la creación de workers de Celery
    mediante prefork.

    :return: Grafo compilado listo para su ejecución.
    """
    uncompiled = build_graph()

    try:
        from psycopg_pool import NullConnectionPool
        
        # Se emplea NullConnectionPool para instanciar conexiones stateless.
        # Esto mitiga colisiones de thread-safety inherentes al forking de Celery (prefork)
        # y previene PoolTimeouts causados por la recolección agresiva de idle SSL connections en Supabase.
        pool = NullConnectionPool(
            conninfo=SUPABASE_CONN_STRING,
            max_size=3,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            },
        )
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
        logger.info("Postgres checkpointer initialized (NullConnectionPool)")
    except Exception as e:
        logger.error(
            f"Failed to initialize Postgres checkpointer: {e}. "
            "Falling back to in-memory (NOT suitable for production)."
        )
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    compiled = uncompiled.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )

    logger.info(
        "AIPost graph compiled: 8 nodes "
        "(supervisor + 6 agents + human_review), "
        "interrupt_before=['human_review']"
    )
    return compiled


aipost_graph = compile_graph()
aipost_graph.get_graph().draw_mermaid_png(output_file_path="final_mutiagent_graph.png")
