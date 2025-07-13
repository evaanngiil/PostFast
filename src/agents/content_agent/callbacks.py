from typing import Any, Dict
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableConfig

class TokenUsageCallback(BaseCallbackHandler):
    """
    Un Callback Handler personalizado que rastrea el uso de tokens de Gemini
    y lo almacena en el estado del grafo.
    """
    def __init__(self, state: Dict[str, Any]):
        # El callback mantiene una referencia al diccionario del estado
        self._state = state
        self._current_node = "unknown_node"

    def set_current_node(self, node_name: str):
        """Los nodos llaman a este método para identificarse antes de ejecutar el LLM."""
        self._current_node = node_name

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> Any:
        """
        Este método se invoca automáticamente cada vez que una llamada al LLM finaliza.
        """
        try:
            print(f"--- [Token Debug] Node: {self._current_node} | LLM Output: {response.llm_output} ---")
            
            # Intentar diferentes formatos de token_usage que puede devolver Gemini
            token_usage = None
            if response.llm_output:
                # Formato 1: token_usage directo
                token_usage = response.llm_output.get("token_usage", {})
                if not token_usage:
                    # Formato 2: usage_info
                    token_usage = response.llm_output.get("usage_info", {})
                if not token_usage:
                    # Formato 3: usage
                    token_usage = response.llm_output.get("usage", {})
            
            total_tokens = 0
            if token_usage:
                # Intentar diferentes claves para total_tokens
                total_tokens = token_usage.get("total_tokens", 0)
                if not total_tokens:
                    total_tokens = token_usage.get("total_tokens_used", 0)
                if not total_tokens:
                    total_tokens = token_usage.get("total", 0)

            print(f"--- [Token Debug] Extracted tokens: {total_tokens} from usage: {token_usage} ---")

            if total_tokens > 0:
                # 1. Acumular el uso de tokens para el nodo actual
                current_node_usage = self._state["token_usage_by_node"].get(self._current_node, 0)
                self._state["token_usage_by_node"][self._current_node] = current_node_usage + total_tokens
                
                # 2. Acumular en el total global del grafo
                self._state["total_tokens"] += total_tokens

                print(f"--- [Token Usage] Node: {self._current_node} | Tokens Used: {total_tokens} | Graph Total: {self._state['total_tokens']} ---")
            else:
                print(f"--- [Token Warning] No tokens detected for node: {self._current_node} ---")
        except Exception as e:
            # No queremos que un error en el callback detenga el grafo
            print(f"Error en TokenUsageCallback: {e}")
            import traceback
            traceback.print_exc()

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