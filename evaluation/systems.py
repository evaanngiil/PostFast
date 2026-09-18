"""
Sistemas bajo evaluación:

- aipost:            pipeline multi-agente completo (grafo LangGraph in-process,
                     checkpointer en memoria, hasta la pausa de human_review).
- aipost_no_<X>:     variantes de ablación (capacidades desactivadas vía estado).
- baseline_context:  el MISMO modelo con el MISMO contexto estático en un único
                     prompt ("LLM + contexto", el competidor a batir).
- baseline_vanilla:  el mismo modelo sin contexto corporativo alguno.

Todas las generaciones devuelven un dict homogéneo con contenido, latencia y tokens.
"""
import os
import time
import uuid
from typing import Optional

# La evaluación corre el grafo in-process: checkpointer en memoria SIEMPRE.
os.environ.setdefault("AIPOST_CHECKPOINTER", "memory")

from src.core.constants import SMART_LLM, GENAI_API_KEY  # noqa: E402
from src.core.logger import logger  # noqa: E402
from evaluation.contexts import build_shared_context, load_company_profile  # noqa: E402

try:
    from langchain_core.callbacks import get_usage_metadata_callback
except ImportError:
    get_usage_metadata_callback = None

_compiled_graph = None

ABLATABLE = (
    "engagement_analyzer",
    "persona_analyst",
    "duplicate_detector",
    "trend_researcher",
    "fact_checker",
    "safety_guard",
    "research_loop",
)


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        from src.agents.multi_agent.graph import compile_graph
        _compiled_graph = compile_graph()
    return _compiled_graph


def _timed(fn):
    """Ejecuta fn midiendo latencia y tokens. Devuelve (result, latency_s, usage)."""
    usage = {}
    start = time.monotonic()
    if get_usage_metadata_callback is not None:
        with get_usage_metadata_callback() as cb:
            result = fn()
        meta = cb.usage_metadata
        usage = {
            "total_input_tokens": sum((u or {}).get("input_tokens", 0) for u in meta.values()),
            "total_output_tokens": sum((u or {}).get("output_tokens", 0) for u in meta.values()),
        }
        usage["total_tokens"] = usage["total_input_tokens"] + usage["total_output_tokens"]
    else:
        result = fn()
    return result, round(time.monotonic() - start, 2), usage


def generate_with_aipost(prompt: str, org_urn: str, ablation_disabled: Optional[list] = None) -> dict:
    """
    Ejecuta el pipeline multi-agente completo hasta la pausa de revisión humana
    y devuelve el borrador validado (fact-checked + safety-checked).
    """
    from src.services.api_client import get_company_profile, get_engagement_insights

    graph = _get_graph()
    thread_id = f"eval-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "linkedin_access_token": "",
        "user_post_idea": prompt,
        "selected_account": {"urn": org_urn},
        "ablation_disabled": list(ablation_disabled or []),
        "knowledge_indexed": True,
    }

    # Precarga desde Supabase (mismo comportamiento que content_generation_task)
    stored = get_company_profile(org_urn) or {}
    profile = stored.get("company_profile") or stored.get("company_profile_data")
    if isinstance(profile, dict) and profile:
        profile.setdefault("urn", org_urn)
        initial_state["company_profile"] = profile
        if profile.get("brand_persona_json"):
            initial_state["brand_persona_json"] = profile["brand_persona_json"]
    else:
        raise RuntimeError(
            f"No hay company_profile en Supabase para {org_urn}. "
            "Ejecuta primero la extracción batch de la organización."
        )

    engagement = get_engagement_insights(org_urn) or {}
    if engagement.get("aggregate_metrics"):
        initial_state["engagement_insights"] = engagement
    if engagement.get("top_performing_posts"):
        initial_state["top_performing_posts"] = engagement["top_performing_posts"]
    if engagement.get("engagement_analysis"):
        initial_state["engagement_analysis"] = engagement["engagement_analysis"]

    def _run():
        result_state = graph.invoke(initial_state, config=config)
        snapshot = graph.get_state(config)
        if not (snapshot.next and "human_review" in snapshot.next):
            logger.warning("[eval] El grafo terminó sin pausa de human_review (thread=%s).", thread_id)
        draft = result_state.get("draft_post") or {}
        return {
            "content": (draft.get("content") or "").replace("\\n", "\n"),
            "hashtags": draft.get("hashtags") or [],
            "fact_check_report": result_state.get("fact_check_report"),
            "safety_report": result_state.get("safety_report"),
            "industry_trends_used": bool(result_state.get("industry_trends")),
            "duplicates_found": len(result_state.get("existing_posts_on_topic") or []),
        }

    result, latency, usage = _timed(_run)
    return {**result, "latency_s": latency, "token_usage": usage}


BASELINE_CONTEXT_PROMPT = """Eres un Redactor de Contenidos de LinkedIn estrella para la empresa "{company_name}".
Escribe una publicación de LinkedIn pulida, atractiva y adaptada a la plataforma sobre la petición del usuario.

Dispones del siguiente contexto de la empresa. Úsalo para que el post sea fiel a la marca y verídico:

{shared_context}

**Reglas:**
- No inventes datos, cifras ni URLs.
- Añade entre 3 y 5 hashtags estratégicos al final.
- Termina con una llamada a la acción natural.
- Devuelve ÚNICAMENTE el texto final del post, empezando directamente con el gancho (hook).

**Petición del usuario:**
"{prompt}"
"""

BASELINE_VANILLA_PROMPT = """Escribe una publicación de LinkedIn profesional, pulida y atractiva sobre la siguiente petición.
Añade 3-5 hashtags al final y una llamada a la acción. Devuelve únicamente el texto del post.

Petición: "{prompt}"
"""


def _invoke_plain_llm(full_prompt: str) -> str:
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model=SMART_LLM, google_api_key=GENAI_API_KEY, temperature=0.5)
    raw = llm.invoke(full_prompt).content
    if isinstance(raw, list):
        raw = "\n".join(p if isinstance(p, str) else p.get("text", str(p)) for p in raw)
    return raw.strip()


def generate_with_baseline_context(prompt: str, org_urn: str) -> dict:
    """Baseline 'LLM + contexto': mismo modelo, mismo contexto, un solo prompt."""
    profile = load_company_profile(org_urn)
    shared_context = build_shared_context(org_urn, prompt)

    def _run():
        return _invoke_plain_llm(BASELINE_CONTEXT_PROMPT.format(
            company_name=profile.get("name", "la empresa"),
            shared_context=shared_context,
            prompt=prompt,
        ))

    content, latency, usage = _timed(_run)
    return {"content": content, "hashtags": [], "latency_s": latency, "token_usage": usage}


def generate_with_baseline_vanilla(prompt: str, org_urn: str) -> dict:
    """Baseline 'LLM vanilla': mismo modelo, sin contexto corporativo."""
    def _run():
        return _invoke_plain_llm(BASELINE_VANILLA_PROMPT.format(prompt=prompt))

    content, latency, usage = _timed(_run)
    return {"content": content, "hashtags": [], "latency_s": latency, "token_usage": usage}


def generate(system: str, prompt: str, org_urn: str) -> dict:
    """
    Punto de entrada único. Sistemas soportados:
    'aipost', 'baseline_context', 'baseline_vanilla', 'aipost_no_<capacidad>'.
    """
    if system == "aipost":
        return generate_with_aipost(prompt, org_urn)
    if system == "baseline_context":
        return generate_with_baseline_context(prompt, org_urn)
    if system == "baseline_vanilla":
        return generate_with_baseline_vanilla(prompt, org_urn)
    if system.startswith("aipost_no_"):
        capability = system.removeprefix("aipost_no_")
        if capability not in ABLATABLE:
            raise ValueError(f"Capacidad de ablación desconocida: {capability}. Válidas: {ABLATABLE}")
        return generate_with_aipost(prompt, org_urn, ablation_disabled=[capability])
    raise ValueError(f"Sistema desconocido: {system}")
