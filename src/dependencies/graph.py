from fastapi import Request, HTTPException
from src.agents.content_agent.agent import create_workflow

graph = create_workflow()

async def get_graph(request: Request):
    if not graph:
        raise HTTPException(status_code=500, detail="LangGraph is not initialized.")
    return graph
