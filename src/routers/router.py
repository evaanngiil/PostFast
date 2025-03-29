from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from src.core.logger import logger

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

@router.post("/ask")
async def ask_model(request: QueryRequest, fastapi_request: Request):
    """
    Endpoint for asking the LLM model a question using the pre-built chain in `build_chains.py`.

    :param request (QueryRequest): Request containing the query to ask the model.

    :return: Response containing the model's answer.
    """
    
    try:
        app = fastapi_request.app
        graph = app.state.graph

        thread = {"configurable": {"thread_id": "1"}}

        # Crear el formato de entrada correcto
        input_data = {
            "messages": [HumanMessage(content=request.query)]
        }

        response = await graph.ainvoke(input_data, thread)
        
        logger.debug(f"Response: {response}")
        logger.debug(f"Tipo de response: {type(response)}")

        return {"query": request.query, "response": response["output"]}

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))