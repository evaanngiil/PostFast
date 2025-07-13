from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage

from src.agents.content_agent.agent_state import InputState, InternalState, OutputState
from src.agents.utils.build_chains import sample_chain
from src.core.logger import logger

async def execute(state: InputState, config: Optional[RunnableConfig] = None):
    try:
        logger.info("🔄 Ejecutando nodo `execute_sample_chain`...")

        messages = state.get("messages", [])

        for message in messages:
            print("Input state messages: \n")
            logger.debug(message.pretty_print())

        if not messages or not isinstance(messages[-1], HumanMessage):
            raise ValueError("❌ El último mensaje no es un HumanMessage válido")

        logger.debug(f"📥 Último mensaje recibido: {messages[-1].content}")

        # Llamar a la IA de forma asíncrona
        response = await sample_chain.ainvoke({"question": messages[-1].content})

        if not isinstance(response, AIMessage):
            if isinstance(response, str):
                ai_response = AIMessage(content=response)
            else:
                raise ValueError("❌ La respuesta no es válida y no se puede convertir")
        else:
            ai_response = response

        logger.debug(f"📤 Respuesta generada: {ai_response.content}")

        # Devolver la respuesta en el formato correcto para el estado del agente
        return {
            "messages": ai_response,
            "output": ai_response.content
        }

    except Exception as e:
        logger.error(f"⚠ Error al ejecutar nodo `execute_sample_chain`: {str(e)}")
        raise