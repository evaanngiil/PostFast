"""
Construcción del contexto compartido para los baselines de la evaluación.

El baseline "LLM + contexto" recibe EXACTAMENTE la misma información estática
que AIPost tiene disponible (perfil corporativo, brand persona, top-k RAG,
posts recientes), pero en un único prompt y sin capacidades agénticas
(sin investigación autónoma, sin fact-checking correctivo, sin detección de
duplicados, sin bucles de compliance). La diferencia medida entre ambos es,
por tanto, atribuible a la arquitectura y no al acceso a datos.
"""
import json
from typing import Optional

from src.core.logger import logger


def load_company_profile(org_urn: str) -> dict:
    """Recupera el perfil corporativo consolidado desde Supabase."""
    from src.services.api_client import get_company_profile

    stored = get_company_profile(org_urn) or {}
    profile = stored.get("company_profile") or stored.get("company_profile_data") or {}
    if isinstance(profile, str):
        try:
            profile = json.loads(profile)
        except Exception:
            profile = {}
    profile.setdefault("urn", org_urn)
    return profile


def build_shared_context(org_urn: str, prompt: str, rag_limit: int = 5) -> str:
    """
    Ensambla el mismo contexto estático que consume el pipeline de AIPost,
    formateado como texto para inyectar en un único prompt de baseline.
    """
    from src.services.rag_service import search_knowledge
    from src.services.supabase_client import get_supabase_admin

    profile = load_company_profile(org_urn)
    persona = profile.get("brand_persona_json") or {}

    rag_context = "Sin resultados en la base de conocimientos."
    try:
        hits = search_knowledge(query=prompt, org_urn=org_urn, threshold=0.4, limit=rag_limit)
        if hits:
            rag_context = "\n".join(
                f"- [{h.get('source_type', 'kb')}] {h.get('content', '')[:700]}"
                for h in hits
            )
    except Exception as exc:
        logger.warning("[eval] Error recuperando RAG para baseline: %s", exc)

    recent_posts = "Sin historial reciente."
    try:
        sb = get_supabase_admin()
        res = (
            sb.table("posts")
            .select("content, created_at")
            .eq("account_id", org_urn)
            .order("created_at", desc=True)
            .limit(3)
            .execute()
        )
        items = res.data or []
        if items:
            recent_posts = "\n".join(
                f"- ({p.get('created_at', '')[:10]}) {p.get('content', '')[:400]}"
                for p in items
            )
    except Exception as exc:
        logger.warning("[eval] Error recuperando posts recientes para baseline: %s", exc)

    return f"""
**Perfil de la Organización:**
{json.dumps(profile, indent=2, ensure_ascii=False)[:4000]}

**Guía de Tono de Marca (Brand Persona):**
{json.dumps(persona, indent=2, ensure_ascii=False) if persona else "No disponible."}

**Base de Conocimientos de la Empresa (fragmentos relevantes):**
{rag_context}

**Últimos posts publicados en la plataforma:**
{recent_posts}
"""


def get_org_display_name(org_urn: str) -> Optional[str]:
    profile = load_company_profile(org_urn)
    return profile.get("name")
