"""
DTO del resultado del grafo multi-agente de generación de contenido.

Antes este módulo alojaba también el bucle de polling de la UI de Streamlit
(ya retirada). El único artefacto que sigue vivo es el DTO que la tarea de
Celery (`src.tasks`) devuelve al frontend.
"""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ContentGenerationResult:
    """
    Encapsula el resultado del grafo multi-agente.

    :param final_post: Contenido final estructurado del post.
    :param token_usage_per_node: Desglose de consumo de tokens por modelo/nodo.
    :param total_tokens_used: Suma total de tokens consumidos.
    """
    final_post: str
    token_usage_per_node: Dict[str, Any]
    total_tokens_used: int
