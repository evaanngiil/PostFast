"""Módulo de inyección de dependencias para el grafo de LangGraph.

Expone el workflow inicializado para que pueda ser consumido por los endpoints de FastAPI.
"""

from fastapi import Request, HTTPException
from src.agents.content_agent.agent import create_workflow

graph = create_workflow()

async def get_graph(request: Request):
    """
    Provee la instancia activa del grafo de LangGraph.

    Valida que el pipeline esté correctamente inicializado antes de
    inyectarlo en la request.

    :param request: El objeto request de FastAPI.
    :return: La instancia compilada del grafo.
    :raises HTTPException: Si el grafo no pudo ser inicializado (HTTP 500).
    """
    if not graph:
        raise HTTPException(status_code=500, detail="LangGraph is not initialized.")
    return graph
