from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Checkpointer
from langgraph.prebuilt import ToolNode
import asyncio

from src.agents.sample_agent.agent_state import InputState, OutputState, InternalState
from src.agents.sample_agent.nodes.executor import execute
from src.core.logger import logger

def create_workflow(checkpointer: Checkpointer = None):
    """Create the workflow graph synchronously."""
    try:
        logger.info("Creating workflow graph...")
        workflow = StateGraph(InternalState, input=InputState, output=OutputState)
        workflow.add_node("execute", execute)

        workflow.add_edge(START, "execute")
        workflow.add_edge("execute", END)

        if checkpointer is None:
            checkpointer = MemorySaver()
        compiled_graph = workflow.compile(checkpointer=checkpointer)

        logger.info("Workflow graph created successfully")
        return compiled_graph
    except Exception as e:
        logger.error(f"Error creating workflow graph: {e}")
        raise

# Crear una instancia del grafo solo si este archivo se ejecuta directamente
try:
    logger.info("Initializing graph...")
    graph = create_workflow()
    logger.info("Graph initialized successfully")
except Exception as e:
    logger.error(f"Error initializing graph: {e}")
    raise
