"""
Herramientas de RAG basadas en LangChain para los agentes de PostFast.
Permite búsqueda semántica en la base de conocimientos de la organización.
"""
from typing import Optional
from langchain_core.tools import tool
from src.services.rag_service import search_knowledge
from src.core.logger import logger

@tool
def search_company_knowledge(query: str, org_urn: str, source_type: Optional[str] = None) -> str:
    """
    Busca información relevante en la base de conocimientos vectorial de la organización.
    
    Args:
        query: La consulta semántica (ej. "guías de tono", "datos sobre el producto X", "misión corporativa").
        org_urn: El URN único de la organización (disponible en company_profile.urn).
        source_type: Opcional. Filtro de tipo de fuente ('brand_book', 'about_us', 'faq', 'product_catalog', 'linkedin_post', 'pdf_document').
        
    Returns:
        Un string formateado con los resultados semánticos más relevantes encontrados.
    """
    logger.info(f"RAG Tool: Buscando '{query}' para org '{org_urn}' (filtro: {source_type})...")
    
    if not org_urn:
        return "Error: No se proporcionó un org_urn válido para realizar la consulta."
        
    results = search_knowledge(
        query=query,
        org_urn=org_urn,
        source_type=source_type,
        threshold=0.6,
        limit=5
    )
    
    if not results:
        return "No se encontró información relevante en la base de conocimientos para esa consulta."
        
    formatted_results = []
    for i, res in enumerate(results, 1):
        src_t = res.get("source_type", "desconocido")
        src_id = res.get("source_id", "N/A")
        similarity = res.get("similarity", 0.0)
        content = res.get("content", "").strip()
        
        formatted_results.append(
            f"Resultado #{i} [Fuente: {src_t} | ID: {src_id} | Similitud: {similarity:.2%}]\n"
            f"Contenido: {content}\n"
            f"---"
        )
        
    return "\n\n".join(formatted_results)
