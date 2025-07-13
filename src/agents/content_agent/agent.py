from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Checkpointer
from functools import partial
from langgraph.prebuilt import ToolNode
import asyncio
import uuid

from .agent_state import InputState, OutputState, InternalState
from .callbacks import TokenUsageCallback
from .nodes.analyze_audience import analyze_audience
from .nodes.draft_post import draft_post
from .nodes.refine_for_engagement import refine_for_engagement
from .nodes.quality_gate import quality_gate
from .nodes.finalize_and_format import finalize_and_format
from .nodes.extract_final_post import extract_final_post
from .nodes.human_review_gate import human_review_gate

from src.core.logger import logger


def create_workflow(checkpointer: Checkpointer = None):
    """Crea el grafo de workflow de generación de contenido."""
    try:
        logger.info("Creating workflow graph...")
        
        # Si no se proporciona un checkpointer, crear uno por defecto
        if checkpointer is None:
            checkpointer = MemorySaver()
        
        # Definir el estado de trabajo (InternalState) y los de entrada/salida
        graph_builder = StateGraph(InternalState, input=InputState, output=OutputState)

        # Añadir los nodos
        graph_builder.add_node("analyze_audience", analyze_audience)
        graph_builder.add_node("draft_post", draft_post)
        graph_builder.add_node("refine_for_engagement", refine_for_engagement)
        graph_builder.add_node("finalize_and_format", finalize_and_format)
        graph_builder.add_node("extract_final_post", extract_final_post)
        graph_builder.add_node("human_review_gate", human_review_gate)

        # Definir el flujo de trabajo
        graph_builder.set_entry_point("analyze_audience")
        graph_builder.add_edge("analyze_audience", "draft_post")
        graph_builder.add_edge("draft_post", "refine_for_engagement")
        graph_builder.add_edge("refine_for_engagement", "finalize_and_format")
        graph_builder.add_edge("finalize_and_format", "extract_final_post")

        # El extract_final_post va directamente al quality_gate (nodo condicional)
        graph_builder.add_conditional_edges(
            "extract_final_post",
            quality_gate,
            {
                "refine": "refine_for_engagement",
                "end": "human_review_gate"
            }
        )

        # El human_review_gate decide si terminar o refinar basado en feedback humano
        graph_builder.add_conditional_edges(
            "human_review_gate",
            human_review_gate,
            {
                "refine": "refine_for_engagement", # Si hay feedback, vuelve a refinar
                "end": END                        # Si se aprueba, termina
            }
        )
        
        # Compilar con checkpointer para mantener el estado entre nodos
        compiled_graph = graph_builder.compile(checkpointer=checkpointer, interrupt_before=["human_review_gate"])

        compiled_graph.get_graph().draw_mermaid_png(output_file_path="graph.png")
        logger.info("Workflow graph created successfully")
        return compiled_graph
    except Exception as e:
        logger.error(f"Error creating workflow graph: {e}")
        raise

