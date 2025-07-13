from typing import TypedDict, Optional, Dict

# --- Estado de Entrada ---
# Define los datos que el grafo ACEPTA al ser invocado.
class InputState(TypedDict):
    query: str
    tone: str
    niche: str
    account_name: str
    link_url: Optional[str]

# --- Estado Interno de Trabajo ---
# Define todos los campos que los agentes pueden leer y escribir.
# Hereda de InputState para tener acceso a los datos iniciales.
class InternalState(InputState):
    creative_brief: Optional[str]
    draft_content: Optional[str]
    refined_content: Optional[str]
    formatted_output: Optional[str]
    final_post: Optional[str] 
    review_notes: Optional[str]
    revision_cycles: Optional[int]
    human_feedback: Optional[str]
    token_usage_by_node: Dict[str, int]
    total_tokens: int

# --- Estado de Salida ---
# Define los datos que el grafo DEVUELVE al finalizar.
class OutputState(TypedDict):
    final_post: str  # Cambiado de final_content a final_post
    total_tokens_used: int

    