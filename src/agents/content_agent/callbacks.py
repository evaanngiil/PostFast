from typing import Any, Dict, List
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult, Generation, ChatGeneration
from langchain_core.runnables import RunnableConfig
import logging

logger = logging.getLogger(__name__)

class TokenUsageCallback(BaseCallbackHandler):
    def __init__(self, state: Dict[str, Any]):
        self._state = state
        self._current_node = "unknown_node"
        if "token_usage_by_node" not in self._state:
            self._state["token_usage_by_node"] = {}
        if "total_tokens" not in self._state:
            self._state["total_tokens"] = 0

    def set_current_node(self, node_name: str):
        self._current_node = node_name

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> Any:
        """
        Este método se invoca al final de cada llamada al LLM.
        Ahora busca en el lugar correcto (`generation.message.usage_metadata`).
        """
        try:
            # La respuesta (`response`) contiene una lista de listas de generaciones.
            if not response.generations:
                return

            tokens_for_this_call = 0
            for generation_list in response.generations:
                for generation in generation_list:
                    # Nos aseguramos de que es una generación de chat
                    if isinstance(generation, ChatGeneration):
                        # Accedemos a la AIMessage y su `usage_metadata`
                        if hasattr(generation, 'message') and hasattr(generation.message, 'usage_metadata'):
                            metadata = generation.message.usage_metadata
                            if metadata and 'total_tokens' in metadata:
                                tokens_for_this_call += metadata['total_tokens']

            if tokens_for_this_call > 0:
                # 1. Acumular el uso de tokens para el nodo actual
                current_node_usage = self._state["token_usage_by_node"].get(self._current_node, 0)
                self._state["token_usage_by_node"][self._current_node] = current_node_usage + tokens_for_this_call
                
                # 2. Acumular en el total global del grafo
                current_total = self._state.get("total_tokens", 0)
                self._state["total_tokens"] = current_total + tokens_for_this_call

                logger.info(f"[Token Usage] Node: {self._current_node} | Tokens: {tokens_for_this_call} | Graph Total: {self._state['total_tokens']}")
            else:
                logger.warning(f"[Token Warning] No tokens detected for node: {self._current_node}. Raw response: {response}")

        except Exception as e:
            logger.error(f"Error in TokenUsageCallback for node {self._current_node}: {e}", exc_info=True)

    def get_token_usage_by_node(self) -> Dict[str, int]:
        return self._state.get("token_usage_by_node", {})

    def get_total_tokens(self) -> int:
        return self._state.get("total_tokens", 0)


def get_token_callback(config: RunnableConfig) -> TokenUsageCallback | None:
    """Función de utilidad para encontrar nuestro callback específico en el manager."""
    # El config["callbacks"] es el objeto AsyncCallbackManager
    callback_manager = config.get("callbacks")
    if callback_manager:
        # Buscamos en la lista de handlers del manager
        for handler in callback_manager.handlers:
            if isinstance(handler, TokenUsageCallback):
                return handler
    return None
