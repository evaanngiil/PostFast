"""
Métricas objetivas de la evaluación comparativa.

Idea central del TFG: los nodos de validación de AIPost (Fact Checker CRAG y
Safety Guard) se usan como INSTRUMENTOS DE MEDICIÓN sobre las salidas de TODOS
los sistemas (incluidos los baselines). Así se cuantifica dónde el baseline
alucina o incumple políticas y AIPost corrige.

Métricas:
- factuality: nº de claims, nº de claims sin evidencia (alucinaciones), tasa de verificación.
- compliance: aprobado/no, severidad, nº de infracciones de política de marca.
- duplication: similitud coseno máxima contra el histórico de posts de la organización.
- forma: longitud, nº de párrafos, nº de hashtags (adecuación al formato LinkedIn).
"""
import re
from typing import Dict, Any

from src.core.logger import logger


def factuality_metrics(content: str, org_urn: str) -> Dict[str, Any]:
    """Ejecuta el Fact Checker (CRAG por claim) como auditor externo del texto."""
    from src.agents.multi_agent.nodes.fact_checker import run_fact_checker_node
    from evaluation.contexts import load_company_profile

    pseudo_state = {
        "draft_post": {"content": content},
        "company_profile": load_company_profile(org_urn),
        "correction_loops": 0,
    }
    try:
        report = run_fact_checker_node(pseudo_state).get("fact_check_report", {})
    except Exception as exc:
        logger.warning("[metrics] Fact checker falló como auditor: %s", exc)
        return {"error": str(exc)}

    claims = report.get("claims", [])
    unverified = [c for c in claims if not c.get("verified")]
    return {
        "n_claims": len(claims),
        "n_unverified_claims": len(unverified),
        "verification_rate": round(1 - len(unverified) / len(claims), 3) if claims else 1.0,
        "overall_pass": report.get("overall_pass", True),
        "evaluated": report.get("evaluated", True),
        "unverified_examples": [c.get("claim", "")[:120] for c in unverified[:3]],
    }


def compliance_metrics(content: str, org_urn: str) -> Dict[str, Any]:
    """Ejecuta el Safety Guard como auditor de políticas de marca del texto."""
    from src.agents.multi_agent.nodes.safety_guard import run_safety_guard_node
    from evaluation.contexts import load_company_profile

    profile = load_company_profile(org_urn)
    pseudo_state = {
        "draft_post": {"content": content},
        "company_profile": profile,
        "brand_persona_json": profile.get("brand_persona_json") or {},
        "correction_loops": 0,
    }
    try:
        report = run_safety_guard_node(pseudo_state).get("safety_report", {})
    except Exception as exc:
        logger.warning("[metrics] Safety guard falló como auditor: %s", exc)
        return {"error": str(exc)}

    severity = (report.get("severity") or "none").lower()
    # 'passes_gate' replica el criterio del pipeline: solo las infracciones con
    # severidad medium/high/critical bloquean una publicación.
    passes_gate = bool(report.get("approved")) or severity in ("none", "low")
    return {
        "approved": report.get("approved", True),
        "passes_gate": passes_gate,
        "severity": severity,
        "n_issues": len(report.get("issues", [])),
        "evaluated": report.get("evaluated", True),
        "issues": [i[:120] for i in report.get("issues", [])[:3]],
    }


def duplication_metrics(content: str, org_urn: str) -> Dict[str, Any]:
    """Similitud semántica máxima contra el histórico de posts de la organización."""
    from src.services.rag_service import search_similar_posts

    try:
        matches = search_similar_posts(query=content[:800], org_urn=org_urn, threshold=0.5, limit=3)
    except Exception as exc:
        logger.warning("[metrics] Duplicación no medible: %s", exc)
        return {"error": str(exc)}

    max_sim = max((m.get("similarity", 0.0) for m in matches), default=0.0)
    return {
        "max_similarity_to_history": round(float(max_sim), 4),
        "n_similar_posts": len(matches),
    }


def form_metrics(content: str) -> Dict[str, Any]:
    """Métricas de forma/estructura adecuadas a LinkedIn (no requieren LLM)."""
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    hashtags = re.findall(r"#\w+", content)
    return {
        "n_chars": len(content),
        "n_paragraphs": len(paragraphs),
        "n_hashtags": len(hashtags),
        "has_question": "?" in content,
        "hashtags_in_range": 3 <= len(hashtags) <= 5,
    }


def compute_all_metrics(content: str, org_urn: str) -> Dict[str, Any]:
    """Calcula el set completo de métricas objetivas para una salida."""
    if not content or not content.strip():
        return {"empty_output": True}
    return {
        "factuality": factuality_metrics(content, org_urn),
        "compliance": compliance_metrics(content, org_urn),
        "duplication": duplication_metrics(content, org_urn),
        "form": form_metrics(content),
    }
