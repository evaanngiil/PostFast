from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.agents.utils.build_chain import sample_chain

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

@router.post("/ask")
async def ask_model(request: QueryRequest):
    """
    Endpoint for asking the LLM model a question using the pre-built chain in `build_chains.py`.

    :param request (QueryRequest): Request containing the query to ask the model.

    :return: Response containing the model's answer.
    """
    
    try:
        response = sample_chain.invoke(request.query)

        return {"query": request.query, "response": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))