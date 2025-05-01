from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.logger import logger
from src.agents.sample_agent.agent import create_workflow
from src.data_processing import setup_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor del ciclo de vida de la aplicación.
    Se ejecuta al iniciar y al cerrar la aplicación.
    """
    try:
        # Inicio de la aplicación
        logger.info("🚀 Iniciando aplicación...")
        
        logger.info("Inicializando Database")
        setup_database()
        logger.info("Database inicializada correctamente")
        
        # Verificar que el grafo está disponible
        app.state.graph = create_workflow()

        logger.info("✅ Grafo inicializado correctamente")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Error durante el inicio de la aplicación: {str(e)}")
        raise
    finally:
        # Limpieza al cerrar
        logger.info("👋 Cerrando aplicación...")
        app.state.graph = None