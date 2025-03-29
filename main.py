from fastapi import FastAPI
from src.routers.router import router
from src.core.lifespan import lifespan
from src.core.logger import logger

app = FastAPI(
    title="PostFast API",
    description="API para el proyecto PostFast con LangGraph",
    lifespan=lifespan
)

try:
    app.include_router(router)
    logger.info("✅ Router incluido correctamente")
except Exception as e:
    logger.error(f"❌ Error al incluir el router: {str(e)}")
    raise e

