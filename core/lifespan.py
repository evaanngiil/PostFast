from contextlib import asynccontextmanager
from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

from logger import logger
from agents.agentes_prueba.agent_1 import sentiment_chain

@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer = MemorySaver()

    agent = await build_model(checkpointer=checkpointer)
    logger.info("Agent built successfully")

    yield {
        "agent": agent,
    }