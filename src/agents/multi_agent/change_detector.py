from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FOLLOWERS_CHANGE_THRESHOLD: int = 50

FOLLOWERS_CHANGE_THRESHOLD: int = 50


@dataclass
class ChangeReport:
    """Resultado de una pasada de deteccion de cambios."""

    has_changes: bool
    reasons: List[str] = field(default_factory=list)

    new_post_urn: Optional[str] = None
    new_post_published_at: Optional[str] = None
    new_follower_count: Optional[int] = None
    new_profile_hash: Optional[str] = None

    def reason_str(self) -> str:
        """CSV legible por humanos de las razones de cambio, ej. 'new_posts,profile_changed'."""
        return ",".join(self.reasons) if self.reasons else ""


def _extract_latest_post(posts: List[Dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
    """
    Retorna (post_urn, published_at_iso) del post mas reciente en la lista.
    Los posts de LinkedIn tipicamente se ordenan del mas nuevo al mas viejo; tomamos el indice 0.
    published_at es un timestamp Unix en milisegundos en la respuesta de la API.
    """
    if not posts:
        return None, None

    post = posts[0]
    urn = post.get("id") or post.get("urn") or post.get("$URN")

    ts = (
        post.get("publishedAt")
        or post.get("createdAt")
        or (post.get("created") or {}).get("time")
    )

    published_at: Optional[str] = None
    if ts is not None:
        try:
            import datetime
            dt = datetime.datetime.fromtimestamp(int(ts) / 1000, tz=datetime.timezone.utc)
            published_at = dt.isoformat()
        except (ValueError, TypeError, OSError):
            published_at = str(ts)

    return urn, published_at


def _compute_profile_hash(org_details: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Calcula un hash MD5 estable de los campos que representan el perfil
    publico de empresa en LinkedIn. Solo incluye campos que un administrador
    puede editar: name, description, specialties, industries, staffCount.

    Usa json.dumps con sort_keys=True para una representacion canonica.
    Retorna None si org_details es None o esta vacio.
    """
    if not org_details:
        return None

    subset = {
        "name": org_details.get("localizedName") or org_details.get("name"),
        "description": org_details.get("localizedDescription") or org_details.get("description"),
        "specialties": sorted(org_details.get("specialties") or []),
        "industries": sorted(
            [str(i) for i in (org_details.get("industries") or [])]
        ),
        "staffCount": org_details.get("staffCount"),
    }

    canonical = json.dumps(subset, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()


def detect_company_changes(
    stored_snapshot: Dict[str, Any],
    fresh_batch: Dict[str, Any],
    followers_threshold: int = FOLLOWERS_CHANGE_THRESHOLD,
) -> ChangeReport:
    """
    Compara un snapshot guardado (fila de company_profiles) contra un batch
    ligero y fresco (posts_count=5 + org_details + follower_count) y
    retorna un ChangeReport describiendo que cambio.

    Parametros
    ----------
    stored_snapshot:
        Dict con claves: last_post_urn, profile_hash, followers_at_last_check.
        Todos los valores pueden ser None (primera ejecucion despues de migracion).

    fresh_batch:
        Dict retornado por get_linkedin_company_batch_data(), con claves:
        organization (dict), posts (list), follower_count (int|None).

    followers_threshold:
        Diferencia absoluta en la cuenta de seguidores que dispara un refresco.
        Por defecto: 50.

    Retorna
    -------
    ChangeReport con has_changes=True si se disparo alguna señal.
    """
    reasons: List[str] = []

    org_details: Optional[Dict[str, Any]] = fresh_batch.get("organization")
    posts: List[Dict[str, Any]] = fresh_batch.get("posts") or []
    fresh_follower_count: Optional[int] = fresh_batch.get("follower_count")

    stored_post_urn: Optional[str] = stored_snapshot.get("last_post_urn")
    fresh_post_urn, fresh_post_published_at = _extract_latest_post(posts)

    if fresh_post_urn and fresh_post_urn != stored_post_urn:
        reasons.append("new_posts")
        logger.info(
            "[change_detector] Nuevo post detectado: guardado=%s nuevo=%s",
            stored_post_urn, fresh_post_urn,
        )

    stored_hash: Optional[str] = stored_snapshot.get("profile_hash")
    fresh_hash: Optional[str] = _compute_profile_hash(org_details)

    if fresh_hash and fresh_hash != stored_hash:
        reasons.append("profile_changed")
        logger.info(
            "[change_detector] Hash de perfil cambiado: guardado=%s nuevo=%s",
            stored_hash, fresh_hash,
        )

    stored_followers: Optional[int] = stored_snapshot.get("followers_at_last_check")

    if (
        fresh_follower_count is not None
        and stored_followers is not None
        and abs(fresh_follower_count - stored_followers) >= followers_threshold
    ):
        reasons.append("followers_changed")
        logger.info(
            "[change_detector] Delta de seguidores >= %d: guardado=%s nuevo=%s",
            followers_threshold, stored_followers, fresh_follower_count,
        )

    return ChangeReport(
        has_changes=len(reasons) > 0,
        reasons=reasons,
        new_post_urn=fresh_post_urn,
        new_post_published_at=fresh_post_published_at,
        new_follower_count=fresh_follower_count,
        new_profile_hash=fresh_hash,
    )
