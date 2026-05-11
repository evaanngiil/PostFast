from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.logger import logger
from src.data_processing import setup_database
from src.agents.multi_agent.graph import aipost_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Hook de gestión del ciclo de vida de la aplicación FastAPI.

    :param app: Instancia principal de la aplicación FastAPI.
    :returns: None
    """
    try:
        # Hook de inicialización de la app.
        logger.info("🚀 Iniciando aplicación...")
        
        logger.info("Inicializando Database")
        setup_database()
        logger.info("Database inicializada correctamente")
        
        # Montaje del state global con el grafo LangGraph (implementación síncrona).
        app.state.graph = aipost_graph
        
        if not app.state.graph:
            raise Exception("LangGraph no inicializado.")
        
        logger.info("✅ LangGraph compilado")
        yield
        
    except Exception as e:
        logger.error(f"❌ Error durante el inicio de la aplicación: {str(e)}")
        raise
    finally:
        # Hook de teardown para liberar recursos al apagar el servidor.
        logger.info("👋 Cerrando aplicación...")
        app.state.graph = None

