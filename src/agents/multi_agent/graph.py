from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
import redis

from state import AgentState
from agents.company_profiler import run_company_profiler_node
from agents.persona_analyst import run_persona_analyst_node
from agents.idea_expander import run_idea_expander_node
from agents.content_writer import run_content_writer_node
from agents.supervisor import supervisor_router, supervisor_router_logic
from src.core.constants import REDIS_HOST, REDIS_PORT

def build_graph():
    """
    Construye el grafo simplificado que comienza directamente con el perfilador.
    """
    workflow = StateGraph(AgentState)

    # Añadir Nodos
    workflow.add_node("company_profiler", run_company_profiler_node)
    workflow.add_node("persona_analyst", run_persona_analyst_node)
    workflow.add_node("idea_expander", run_idea_expander_node)
    workflow.add_node("content_writer", run_content_writer_node)
    workflow.add_node("supervisor", supervisor_router)

    # Definir Flujo de Control
    workflow.set_entry_point("company_profiler")
    
    workflow.add_edge("company_profiler", "supervisor")
    workflow.add_edge("persona_analyst", "supervisor")
    workflow.add_edge("idea_expander", "supervisor")
    workflow.add_edge("content_writer", "supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router_logic,
        {
            "persona_analyst": "persona_analyst",
            "idea_expander": "idea_expander",
            "content_writer": "content_writer",
            "__end__": END
        }
    )
    
    # redis_client = redis.StrictRedis(
    #                 host=REDIS_HOST,
    #                 port=REDIS_PORT,
    #                 decode_responses=True # Decodificar respuestas a UTF-8
    #             )    
    # memory = RedisSaver(redis_client=redis_client)
    memory = None # Temporarily disable RedisSaver due to module error
    return workflow.compile(checkpointer=memory)

aipost_graph = build_graph()
aipost_graph.get_graph().draw_mermaid_png(output_file_path="final_mutiagent_graph.png")
