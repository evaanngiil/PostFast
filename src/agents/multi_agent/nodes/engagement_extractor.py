"""Nodo de extracción de métricas brutas de engagement de LinkedIn

Nodo de LangGraph que obtiene metricas de engagement de las APIs de estadisticas
organizacionales de LinkedIn y calcula las tasas de engagement por post.

Ubicado en el pipeline DESPUES de company_profiler, ANTES de engagement_analyzer.
Lee: company_profile, linkedin_access_token
Escribe: engagement_insights, top_performing_posts
"""

import time
from typing import Dict, Any, List, Optional

from src.agents.multi_agent.state import AgentState
from src.core.logger import logger
from src.social_apis import (
    get_organization_share_statistics,
    get_organization_page_statistics,
    get_organization_follower_statistics,
)


def _compute_engagement_rate(stat: Dict[str, Any]) -> float:
    """Calcula la tasa de engagement para las estadisticas de un solo post.
    
    tasa_engagement = (likes + comentarios + shares + clicks) / impresiones
    Retorna 0.0 si las impresiones son cero.
    """
    total_stats = stat.get("totalShareStatistics", {})
    impressions = total_stats.get("impressionCount", 0) or 0
    if impressions == 0:
        return 0.0

    likes = total_stats.get("likeCount", 0) or 0
    comments = total_stats.get("commentCount", 0) or 0
    shares = total_stats.get("shareCount", 0) or 0
    clicks = total_stats.get("clickCount", 0) or 0
    engagement = likes + comments + shares + clicks
    return round(engagement / impressions, 6)


def _rank_posts_by_engagement(share_stats: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Ordena los posts por tasa de engagement y retorna los top N."""
    enriched = []
    for stat in share_stats:
        total = stat.get("totalShareStatistics", {})
        post_urn = stat.get("share") or stat.get("ugcPost") or "unknown"
        rate = _compute_engagement_rate(stat)
        enriched.append({
            "post_urn": post_urn,
            "engagement_rate": rate,
            "impressions": total.get("impressionCount", 0),
            "likes": total.get("likeCount", 0),
            "comments": total.get("commentCount", 0),
            "shares": total.get("shareCount", 0),
            "clicks": total.get("clickCount", 0),
            "unique_impressions": total.get("uniqueImpressionsCount", 0),
        })

    enriched.sort(key=lambda x: x["engagement_rate"], reverse=True)
    return enriched[:limit]


def _aggregate_metrics(share_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula las metricas agregadas de engagement para todos los posts."""
    total_impressions = 0
    total_engagements = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_clicks = 0
    post_count = len(share_stats)

    for stat in share_stats:
        total = stat.get("totalShareStatistics", {})
        impressions = total.get("impressionCount", 0) or 0
        likes = total.get("likeCount", 0) or 0
        comments = total.get("commentCount", 0) or 0
        shares_count = total.get("shareCount", 0) or 0
        clicks = total.get("clickCount", 0) or 0

        total_impressions += impressions
        total_likes += likes
        total_comments += comments
        total_shares += shares_count
        total_clicks += clicks
        total_engagements += likes + comments + shares_count + clicks

    avg_engagement_rate = (
        round(total_engagements / total_impressions, 6)
        if total_impressions > 0 else 0.0
    )

    return {
        "post_count": post_count,
        "total_impressions": total_impressions,
        "total_engagements": total_engagements,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_clicks": total_clicks,
        "avg_engagement_rate": avg_engagement_rate,
        "avg_impressions_per_post": (
            round(total_impressions / post_count) if post_count > 0 else 0
        ),
    }


def run_engagement_extractor_node(state: AgentState) -> Dict[str, Any]:
    """Nodo de LangGraph: extrae datos de engagement de las APIs de LinkedIn.
    
    Llama a tres endpoints:
    1. organizationalEntityShareStatistics - metricas por post
    2. organizationPageStatistics - vistas/visitantes de pagina
    3. organizationalEntityFollowerStatistics - crecimiento de seguidores
    
    Calcula tasas de engagement, clasifica posts principales y agrega metricas.
    """
    logger.info("Ejecutando extractor de métricas de engagement.")

    company_profile = state.get("company_profile")
    access_token = state.get("linkedin_access_token")

    if not company_profile or not access_token:
        logger.warning("Extractor de engagement: falta company_profile o access_token. Omitiendo.")
        return {
            "engagement_insights": {"error": "missing_prerequisites", "detail": "No company profile or token"},
            "top_performing_posts": [],
        }

    org_urn = company_profile.get("urn", "")
    if not org_urn:
        selected = state.get("selected_account", {})
        org_id = selected.get("org_id") or selected.get("id")
        if org_id:
            org_urn = f"urn:li:organization:{org_id}"
        else:
            logger.error("Extractor de engagement: no se puede determinar el URN de la org.")
            return {
                "engagement_insights": {"error": "no_org_urn"},
                "top_performing_posts": [],
            }

    logger.info(f"Extrayendo datos de engagement para {org_urn}")

    # 1. Analíticas de publicación individuales (Share statistics)
    share_stats = get_organization_share_statistics(
        org_urn=org_urn,
        access_token=access_token,
    )
    logger.info(f"Obtenidos {len(share_stats)} elementos de share stat")

    # 2. Métricas a nivel de página (Page visitors y views)
    page_stats = get_organization_page_statistics(
        org_urn=org_urn,
        access_token=access_token,
    )
    logger.info(f"Obtenidos {len(page_stats)} elementos de page stat")

    # 3. Datos demográficos y crecimiento de audiencia
    follower_stats = get_organization_follower_statistics(
        org_urn=org_urn,
        access_token=access_token,
    )
    logger.info(f"Obtenidos {len(follower_stats)} elementos de follower stat")

    # Computación de métricas consolidadas derivadas
    aggregate = _aggregate_metrics(share_stats)
    top_posts = _rank_posts_by_engagement(share_stats, limit=10)

    engagement_insights = {
        "org_urn": org_urn,
        "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "aggregate_metrics": aggregate,
        "share_statistics": share_stats[:50],
        "page_statistics": page_stats[:20],
        "follower_statistics": follower_stats[:20],
    }

    print(f"Extraccion de engagement completada: {aggregate['post_count']} posts, "
          f"tasa promedio: {aggregate['avg_engagement_rate']:.4f}")

    return {
        "engagement_insights": engagement_insights,
        "top_performing_posts": top_posts,
    }
