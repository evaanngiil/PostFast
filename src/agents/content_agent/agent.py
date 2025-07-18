from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Checkpointer

from .agent_state import InputState, OutputState, InternalState
from .nodes.analyze_audience import analyze_audience
from .nodes.draft_post import draft_post
from .nodes.refine_for_engagement import refine_for_engagement
from .nodes.quality_gate import quality_gate
from .nodes.finalize_and_format import finalize_and_format
from .nodes.extract_final_post import extract_final_post

from src.core.logger import logger

# Esta función es la LÓGICA de enrutamiento, no un nodo. 
def entry_router(state: InternalState) -> str:
    """
    Rutea al inicio del grafo o directamente a refinamiento si hay feedback.
    """
    logger.info(f"Entry Router: Checking for human_feedback. Found: {state.get('human_feedback')}")
    
    if state.get("human_feedback"):
        logger.info("Entry Router: Feedback found, routing to 'refine_for_engagement'.")
        return "refine_for_engagement"
    else:
        logger.info("Entry Router: No feedback, routing to 'analyze_audience'.")
        return "analyze_audience"


def create_workflow(checkpointer: Checkpointer = None):
    """Crea el grafo de workflow de generación de contenido."""
    try:
        logger.info("Creating workflow graph...")
        
        if checkpointer is None:
            checkpointer = MemorySaver()
        
        graph_builder = StateGraph(InternalState, input=InputState, output=OutputState)

        graph_builder.add_node("analyze_audience", analyze_audience)
        graph_builder.add_node("draft_post", draft_post)
        graph_builder.add_node("refine_for_engagement", refine_for_engagement)
        graph_builder.add_node("finalize_and_format", finalize_and_format)
        graph_builder.add_node("extract_final_post", extract_final_post)
        # quality_gate no es un nodo, es la lógica para un arco condicional.


        # Desde el inicio, usamos nuestra función `entry_router` para decidir a dónde ir.
        graph_builder.add_conditional_edges(
            START,
            entry_router, # La función que toma la decisión
            {
                # El mapeo de la salida de la función al nombre del nodo
                "analyze_audience": "analyze_audience",
                "refine_for_engagement": "refine_for_engagement"
            }
        )
        
        # Flujo normal desde el inicio
        graph_builder.add_edge("analyze_audience", "draft_post")
        graph_builder.add_edge("draft_post", "refine_for_engagement")
        
        # Flujo de refinamiento y finalización
        graph_builder.add_edge("refine_for_engagement", "finalize_and_format")
        graph_builder.add_edge("finalize_and_format", "extract_final_post")
        
        # Después de extraer el post, vamos a la puerta de calidad (que es una decisión, no un nodo).
        graph_builder.add_conditional_edges(
            "extract_final_post",
            quality_gate,
            {
                "refine": "refine_for_engagement", # Volver a refinar
                "end": END                        # Aprobar y terminar
            }
        )

        # Compilar el grafo.
        compiled_graph = graph_builder.compile(checkpointer=checkpointer)
        
        try:
            # compiled_graph.get_graph().draw_mermaid_png(output_file_path="graph_v3_fixed.png")
            logger.info("Corrected workflow graph 'graph_v3_fixed.png' generated.")
        except Exception as e:
            logger.warning(f"Could not generate graph image: {e}")

        logger.info("Workflow graph created successfully with correct conditional entry point.")
        return compiled_graph
    except Exception as e:
        logger.error(f"Error creating workflow graph: {e}", exc_info=True)
        raise