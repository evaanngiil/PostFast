"""
Nodo Duplicate Detector para PostFast.
Se encarga de evaluar si la cuenta de LinkedIn ya cuenta con publicaciones
previas similares a la temática propuesta por el usuario, inyectando el 
contexto correspondiente en el estado del grafo para evitar repeticiones.
"""
from typing import Dict, Any
from src.agents.multi_agent.state import AgentState
from src.services.rag_service import search_similar_posts
from src.core.logger import logger

def run_duplicate_detector_node(state: AgentState) -> Dict[str, Any]:
    print("--- 🔍 EJECUTANDO DETECTOR DE DUPLICADOS ---")
    logger.info("=== DUPLICATE DETECTOR: start ===")
    
    user_idea = state.get("user_post_idea", "")
    company_profile = state.get("company_profile", {})
    org_urn = company_profile.get("urn", "")
    
    if not org_urn or not user_idea:
        logger.warning("Duplicate detector: faltan datos (org_urn o user_post_idea).")
        return {
            "existing_posts_on_topic": [],
            "duplicate_context": "No se pudo realizar el análisis de duplicados por falta de datos base.",
        }
    
    # Búsqueda semántica de posts publicados con un umbral moderado para capturar temas relacionados
    similar_posts = search_similar_posts(
        query=user_idea,
        org_urn=org_urn,
        threshold=0.60,
        limit=5,
    )
    
    if not similar_posts:
        logger.info("No se encontraron posts similares. Tema editorialmente fresco.")
        print("✅ Tema novedoso para la organización (0 coincidencias).")
        return {
            "existing_posts_on_topic": [],
            "duplicate_context": "TEMA NUEVO: La organización no ha publicado contenido similar sobre este tema en el histórico de LinkedIn analizado. Tienes total libertad creativa.",
        }
    
    # Construcción detallada de contexto para el redactor
    context_parts = [
        "⚠️ ALERTA DE COHERENCIA EDITORIAL (POSTS EXISTENTES ENCONTRADOS):",
        "El tema propuesto es similar a publicaciones que ya se realizaron en el perfil de LinkedIn. ",
        "Para evitar ser repetitivo, abarca un nuevo ángulo, expande lo ya dicho o responde a dudas que hayan quedado pendientes.",
        "A continuación se detallan los posts previos similares encontrados en la base de datos:\n"
    ]
    
    for i, post in enumerate(similar_posts, 1):
        pub_date = post.get("published_at")
        pub_str = pub_date.strftime("%Y-%m-%d") if pub_date and hasattr(pub_date, "strftime") else str(pub_date or "N/A")
        
        context_parts.append(
            f"Post #{i} (Similitud Semántica: {post.get('similarity', 0):.2%})\n"
            f"  - Fecha de Publicación: {pub_str}\n"
            f"  - Tasa de Engagement: {post.get('engagement_rate', 0.0):.4%}\n"
            f"  - Tema Dominante: {post.get('dominant_topic', 'N/A')}\n"
            f"  - Contenido: \"{post.get('content', '')[:250]}...\"\n"
        )
    
    context = "\n".join(context_parts)
    print(f"✅ Búsqueda finalizada. Encontrados {len(similar_posts)} posts relacionados.")
    logger.info(f"=== DUPLICATE DETECTOR: completed ({len(similar_posts)} matches) ===")
    
    return {
        "existing_posts_on_topic": similar_posts,
        "duplicate_context": context,
    }
