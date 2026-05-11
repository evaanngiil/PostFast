import streamlit as st

from src.social_apis import (
    get_linkedin_organization_follower_count,
    get_organization_share_statistics,
    get_linkedin_posts,
)
from src.core.logger import logger


def _get_access_token() -> str | None:
    """
    Resuelve heurísticamente el access token de LinkedIn en el contexto de UI.

    :returns: String del JWT, o None si la sesión no contiene credentials.
    """
    token = st.session_state.get("auth_token_for_url")
    if not token:
        td = st.session_state.get("li_token_data")
        if isinstance(td, dict):
            token = td.get("access_token")
    return token


def _is_organization_urn(urn: str) -> bool:
    """
    Filtro de seguridad que previene colisiones HTTP 400/403 al llamar endpoints
    de LinkedIn exclusivos para organizaciones (y no para perfiles de persona).

    :param urn: Cadena identificadora del ente.
    :returns: True si el prefijo corresponde a una organización válida.
    """
    return isinstance(urn, str) and urn.startswith("urn:li:organization:")


@st.cache_data(ttl=300, show_spinner=False)
def get_live_follower_count(org_urn: str, access_token: str) -> int | None:
    """
    Extrae la audiencia global consolidada (follower count) en tiempo real.

    :param org_urn: Cadena identificadora del ente.
    :param access_token: Token de sesión.
    :returns: Volumen entero de la red de seguidores, o None si hay error.
    """
    if not _is_organization_urn(org_urn):
        return None
    try:
        count = get_linkedin_organization_follower_count(org_urn, access_token)
        logger.debug(f"[live] Conteo de seguidores para {org_urn}: {count}")
        return count
    except Exception as e:
        logger.error(f"[live] Error obteniendo conteo de seguidores para {org_urn}: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_live_engagement_insights(org_urn: str, access_token: str) -> dict | None:
    """
    Agrega analíticas predictivas llamando al endpoint de shares de LinkedIn.

    Computa tasas derivadas como el engagement rate ponderando inputs transaccionales
    (likes, shares, clicks, impresiones).

    :param org_urn: Cadena identificadora del ente.
    :param access_token: Token de sesión.
    :returns: Diccionario mapeado de Insights (total_impressions, avg_engagement_rate, etc).
    """
    if not _is_organization_urn(org_urn):
        return None
    try:
        elements = get_organization_share_statistics(org_urn, access_token)
        if not elements:
            return None

        total_impressions = 0
        total_likes = 0
        total_comments = 0
        total_shares = 0
        total_clicks = 0

        for el in elements:
            stats = el.get("totalShareStatistics") or {}
            total_impressions += stats.get("impressionCount", 0)
            total_likes += stats.get("likeCount", 0)
            total_comments += stats.get("commentCount", 0)
            total_shares += stats.get("shareCount", 0)
            total_clicks += stats.get("clickCount", 0)

        total_engagements = total_likes + total_comments + total_shares + total_clicks
        avg_engagement_rate = (
            round(total_engagements / total_impressions * 100, 2)
            if total_impressions > 0
            else 0.0
        )

        result = {
            "total_impressions": total_impressions,
            "avg_engagement_rate": avg_engagement_rate,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_engagements": total_engagements,
        }
        logger.debug(f"[live] Insights de engagement para {org_urn}: {result}")
        return result

    except Exception as e:
        logger.error(f"[live] Error obteniendo insights de engagement para {org_urn}: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_live_posts_count(org_urn: str, access_token: str) -> int:
    """
    Calcula el inventario de publicaciones de la organización mediante un ping directo al source.

    :param org_urn: Cadena identificadora del ente.
    :param access_token: Token de sesión.
    :returns: Integer con el conteo de elementos recibidos por API (max. 100).
    """
    if not _is_organization_urn(org_urn):
        return 0
    try:
        posts = get_linkedin_posts(access_token, target_urn=org_urn, count=100, start=0)
        count = len(posts) if posts else 0
        logger.debug(f"[live] Conteo de posts para {org_urn}: {count}")
        return count
    except Exception as e:
        logger.error(f"[live] Error obteniendo conteo de posts para {org_urn}: {e}")
        return 0
