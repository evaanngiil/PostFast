"""
Módulo principal que define y compila el StateGraph para el pipeline multi-agente de AIPost.

Construye el workflow de generación de contenido conectando los nodos de PostFast v2:
supervisor, company_profiler, knowledge_ingester, engagement_extractor, engagement_analyzer,
persona_analyst, duplicate_detector, trend_researcher, idea_expander, content_writer,
content_editor, fact_checker, safety_guard y human_review.

El supervisor ejecuta el ruteo determinista a través de conditional edges
(supervisor_router_logic) sin llamadas a LLM.

El nodo human_review actúa como un interrupt_before: LangGraph pausa la ejecución
antes de entrar, permitiendo que la tarea de Celery detecte la pausa
y devuelva el borrador para la revisión del usuario.

Checkpointer:
- Por defecto: psycopg_pool.ConnectionPool + PostgresSaver apuntando al puerto de
  transacción de Supavisor (6543) con prepare_threshold=0. Si falla, la aplicación
  ABORTA (fail-fast): degradar silenciosamente a memoria rompería el HITL en
  despliegues multi-worker.
- AIPOST_CHECKPOINTER=memory: MemorySaver explícito para tests y evaluación offline.
"""

from __future__ import annotations

import os

from langgraph.graph import StateGraph, START, END

from src.agents.multi_agent.state import AgentState
from src.agents.multi_agent.nodes.supervisor import (
    supervisor_router,
    supervisor_router_logic,
)
from src.agents.multi_agent.nodes.engagement_analyzer import (
    run_engagement_analyzer_node,
)
from src.agents.multi_agent.nodes.persona_analyst import (
    run_persona_analyst_node,
)
from src.agents.multi_agent.nodes.duplicate_detector import (
    run_duplicate_detector_node,
)
from src.agents.multi_agent.nodes.trend_researcher import (
    run_trend_researcher_node,
)
from src.agents.multi_agent.nodes.idea_expander import (
    run_idea_expander_node,
)
from src.agents.multi_agent.nodes.content_writer import (
    run_content_writer_node,
)
from src.agents.multi_agent.nodes.content_editor import (
    run_content_editor_node,
)
from src.agents.multi_agent.nodes.fact_checker import (
    run_fact_checker_node,
)
from src.agents.multi_agent.nodes.safety_guard import (
    run_safety_guard_node,
)

from src.core.constants import SUPABASE_CONN_STRING
from src.core.logger import logger

# Nodos "worker" que devuelven el control al supervisor tras ejecutarse.
WORKER_NODES = (
    "engagement_analyzer",
    "persona_analyst",
    "duplicate_detector",
    "trend_researcher",
    "idea_expander",
    "content_writer",
    "content_editor",
    "fact_checker",
    "safety_guard",
)


def human_review_node(state: AgentState) -> dict:
    """
    Gestiona la pausa de revisión humana evaluando el feedback proporcionado por el usuario.

    Si se recibe feedback, limpia el payload del borrador actual para que el
    supervisor derive la petición al Content Editor, y resetea el contador de
    bucles de corrección: cada iteración humana abre un nuevo presupuesto de
    validación automática (fact check / safety).

    :param state: Estado actual del grafo que contiene los datos del pipeline y el feedback.
    :return: Diccionario con la actualización parcial del estado.
    """
    feedback = state.get("user_feedback")
    if feedback:
        logger.info(
            "--- human_review: feedback recibido ('%s…'), "
            "clearing draft_post for regeneration ---",
            feedback[:60],
        )
        current_draft = state.get("draft_post", {}).get("content", "") if state.get("draft_post") else ""
        return {
            "draft_post": None,
            "last_draft_content": current_draft,
            "correction_loops": 0,
        }

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


def build_graph(node_overrides: dict | None = None) -> StateGraph:
    """
    Ensambla la topología completa del grafo LangGraph con sus respectivos nodos y edges.

    :param node_overrides: Diccionario opcional {nombre_nodo: callable} que permite
                           sustituir implementaciones de nodos (tests de integración
                           sin llamadas LLM reales).
    :return: Instancia de StateGraph no compilada con el workflow definido.
    """
    default_nodes = {
        "supervisor":           supervisor_router,
        "engagement_analyzer":  run_engagement_analyzer_node,
        "persona_analyst":      run_persona_analyst_node,
        "duplicate_detector":   run_duplicate_detector_node,
        "trend_researcher":     run_trend_researcher_node,
        "idea_expander":        run_idea_expander_node,
        "content_writer":       run_content_writer_node,
        "content_editor":       run_content_editor_node,
        "fact_checker":         run_fact_checker_node,
        "safety_guard":         run_safety_guard_node,
        "human_review":         human_review_node,
    }
    if node_overrides:
        default_nodes.update(node_overrides)

    graph = StateGraph(AgentState)

    for name, fn in default_nodes.items():
        graph.add_node(name, fn)

    # Inicio del Grafo
    graph.add_edge(START, "supervisor")

    # Enrutamiento condicional desde el supervisor central
    graph.add_conditional_edges(
        "supervisor",
        supervisor_router_logic,
        {name: name for name in (*WORKER_NODES, "human_review")},
    )

    # Edges de retorno de cada worker al supervisor
    for name in WORKER_NODES:
        graph.add_edge(name, "supervisor")

    # Edge de salida o re-ciclo tras revisión humana
    graph.add_conditional_edges(
        "human_review",
        _human_review_router,
        {
            "supervisor": "supervisor",
            "__end__": END,
        },
    )

    return graph


def _build_checkpointer():
    """
    Construye el checkpointer según configuración.

    - AIPOST_CHECKPOINTER=memory -> MemorySaver (tests / evaluación offline).
    - Por defecto -> PostgresSaver con ConnectionPool (fail-fast si no conecta).
    """
    mode = os.getenv("AIPOST_CHECKPOINTER", "postgres").lower()

    if mode == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        logger.info("Checkpointer en MEMORIA (AIPOST_CHECKPOINTER=memory): solo para tests/evaluación.")
        return MemorySaver()

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    # ConnectionPool configurado con prepare_threshold=0.
    # Obligatorio para soportar el modo transacción de Supavisor (puerto 6543)
    # permitiendo pooling eficiente en entornos productivos multi-worker.
    pool = ConnectionPool(
        conninfo=SUPABASE_CONN_STRING,
        min_size=1,
        max_size=10,
        max_idle=60,
        max_lifetime=300,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,  # CRÍTICO: El re-route de transacciones en Supavisor rompe sentencias preparadas
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    logger.info("Postgres checkpointer initialized (psycopg_pool.ConnectionPool)")
    return checkpointer


def compile_graph(node_overrides: dict | None = None):
    """
    Inicializa el checkpointer y compila el StateGraph final.

    IMPORTANTE: si el checkpointer de Postgres falla, se propaga la excepción
    (fail-fast). Degradar silenciosamente a memoria rompería el Human-in-the-Loop
    en despliegues Celery multi-worker (la tarea de resume caería en un worker
    sin acceso al estado pausado).

    :return: Grafo compilado listo para su ejecución.
    """
    uncompiled = build_graph(node_overrides)
    checkpointer = _build_checkpointer()

    compiled = uncompiled.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )

    logger.info(
        "AIPost graph compiled: %d nodes (supervisor + workers + human_review), "
        "interrupt_before=['human_review']",
        len(WORKER_NODES) + 2,
    )
    return compiled


class ForkSafeGraphWrapper:
    """
    Compila el grafo de forma perezosa y por-proceso: los workers de Celery con
    prefork no pueden compartir el ConnectionPool del proceso padre, así que se
    recompila al detectar un PID distinto.
    """

    def __init__(self):
        self._compiled_graph = None
        self._pid = None

    def _get_graph(self):
        current_pid = os.getpid()
        if self._compiled_graph is None or self._pid != current_pid:
            logger.info(f"ForkSafeGraphWrapper: (Re)compiling graph for PID {current_pid} (previous: {self._pid})")
            self._compiled_graph = compile_graph()
            self._pid = current_pid
        return self._compiled_graph

    def invoke(self, *args, **kwargs):
        return self._get_graph().invoke(*args, **kwargs)

    def get_state(self, *args, **kwargs):
        return self._get_graph().get_state(*args, **kwargs)

    def update_state(self, *args, **kwargs):
        return self._get_graph().update_state(*args, **kwargs)

    def get_state_history(self, *args, **kwargs):
        return self._get_graph().get_state_history(*args, **kwargs)

    def stream(self, *args, **kwargs):
        return self._get_graph().stream(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._get_graph(), name)


aipost_graph = ForkSafeGraphWrapper()

# NOTA: el diagrama Mermaid del grafo ya NO se genera al importar este módulo
# (efecto secundario que abría conexiones y escribía ficheros en cada import).
# Para regenerarlo: `python scripts/draw_graph.py`.
