# Construye un CompanyProfile consolidado mediante:
#   1. Batch request a LinkedIn API (datos corporativos y posteos)
#   2. Batch LLM Inference (1 llamada para todos los posteos)
#   3. Scraping asíncrono para completitud y enriquecimiento
#   4. Persistencia en dos fases (Fase A: pre-LLM, Fase B: post-LLM)

# State output: state["company_profile"]

from __future__ import annotations

import datetime
import re
import time
from src.core.logger import logger
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.agents.multi_agent.state import AgentState, CompanyProfile
from src.core.constants import ANALYSIS_LLM, MEDIUM_LLM, GENAI_API_KEY
from src.social_apis import get_linkedin_company_batch_data


def _llm_invoke_with_retry(
    chain: Any,
    inputs: Dict[str, Any],
    max_retries: int = 5,
    base_delay: float = 60.0,
    max_delay: float = 300.0,
) -> Any:
    """
    Invoca una cadena LangChain con retroceso exponencial en 429 / ResourceExhausted.

    Captura:
      - google.api_core.exceptions.ResourceExhausted  (Cuota de Gemini excedida)
      - Cualquier excepcion cuyo str() contenga '429' (fallback para errores envueltos)

    Reintenta hasta max_retries veces. El retraso comienza en base_delay segundos y
    se duplica en cada intento, hasta un maximo de max_delay.
    Lanza la ultima excepcion si se agotan todos los reintentos.
    """
    try:
        from google.api_core.exceptions import ResourceExhausted
        _quota_exc: tuple = (ResourceExhausted,)
    except ImportError:
        _quota_exc = ()

    delay = base_delay
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt in range(max_retries):
        try:
            return chain.invoke(inputs)
        except Exception as exc:
            is_quota = (
                (_quota_exc and isinstance(exc, _quota_exc))
                or "429" in str(exc)
                or "quota" in str(exc).lower()
                or "resource exhausted" in str(exc).lower()
            )
            if not is_quota:
                raise  # non-quota errors propagate immediately
            last_exc = exc
            if attempt < max_retries - 1:
                logger.warning(
                    "[llm_retry] 429/ResourceExhausted — reintentando en %.0fs "
                    "(intento %d/%d): %s",
                    delay, attempt + 1, max_retries, exc,
                )
                time.sleep(delay)
                delay = min(delay * 2, max_delay)
            else:
                logger.error(
                    "[llm_retry] Se agotaron los %d reintentos para la llamada LLM: %s",
                    max_retries, exc,
                )
    raise last_exc


# Pydantic schemas

class PostAnalysis(BaseModel):
    """Resumen + opinion editorial para un solo post de LinkedIn."""
    post_id: str = Field(description="URN o ID del post.")
    published_at: Optional[str] = Field(
        default=None,
        description="Fecha de publicacion en formato ISO-8601, si esta disponible.",
    )
    summary: str = Field(
        description=(
            "Concise 2-3 sentence summary of the post: "
            "what it is about, what message it conveys, and what format it uses."
        )
    )
    opinion: str = Field(
        description=(
            "Brief editorial opinion (1-2 sentences) about the post's quality and effectiveness: "
            "clarity of message, audience engagement, and potential improvements."
        )
    )
    dominant_topic: str = Field(
        description="Dominant topic of the post in 3-5 words (e.g. 'product launch', 'company culture').",
    )
    tone: str = Field(
        description="Predominant tone of the post (e.g. 'informative', 'inspirational', 'commercial', 'educational').",
    )


class PostAnalysisBatch(BaseModel):
    """Batch result: analyses for ALL posts in a single LLM call."""
    analyses: List[PostAnalysis] = Field(
        description="One PostAnalysis per post, in the same order as the input."
    )


class ExtractedLinkedInData(BaseModel):
    """Structured data extracted from the public LinkedIn company page."""
    followers: Optional[str] = Field(default=None, description="Follower count as shown on the page.")
    about_us: Optional[str] = Field(default=None, description="Full text of the 'About us' section.")
    industry: Optional[str] = Field(default=None, description="Company industry or sector.")
    company_size: Optional[str] = Field(default=None, description="Company size (e.g. '11-50 employees').")
    headquarters: Optional[str] = Field(default=None, description="City and region of headquarters.")
    company_type: Optional[str] = Field(default=None, description="Company type (e.g. 'Privately Held').")
    founded: Optional[str] = Field(default=None, description="Year the company was founded.")
    specialties: Optional[List[str]] = Field(default=None, description="List of company specialties.")


# Prompts

_POST_ANALYSIS_SYSTEM = (
    "You are a B2B content marketing expert specialised in LinkedIn. "
    "Analyse each post objectively and precisely. "
    "Reply ONLY with the requested structured JSON, no extra text."
)

# BATCH prompt: recibe N posts numerados y devuelve una lista de PostAnalysis.
# Una sola llamada LLM para todos los posts -> resuelve el limite RPD del free tier.
_POST_ANALYSIS_BATCH_HUMAN = """\
Analyse the following {n} LinkedIn posts published by '{company_name}'.
For each post return a PostAnalysis object in the 'analyses' list, in the same order.

{posts_block}

For every PostAnalysis:
- post_id: use the id provided in each POST header.
- published_at: use the date provided in each POST header (ISO-8601).
- summary: 2-3 concise sentences.
- opinion: 1-2 editorial sentences on effectiveness.
- dominant_topic: 3-5 words.
- tone: one or two words.
"""

_SCRAPE_EXTRACTION_SYSTEM = (
    "You are a high-precision data extraction system. "
    "Extract ONLY the requested fields from the text. "
    "Return null for any field not found. "
    "Ignore cookie banners, navigation menus, footers, ads, and legal text."
)

_SCRAPE_EXTRACTION_HUMAN = """\
Extract key information from the following scraped LinkedIn company page text.

--- TEXT ---
{scraped_content}
--- END ---
"""


# Helpers: post parsing

def _extract_post_text(post: Dict[str, Any]) -> str:
    """
    Extrae texto legible de un elemento /posts de la API de LinkedIn.
    Maneja /posts v2 (campo commentary) y ugcPosts heredados (specificContent).
    """
    if commentary := post.get("commentary"):
        return commentary

    specific = post.get("specificContent", {})
    share_media = specific.get("com.linkedin.ugc.ShareContent", {})
    if text := share_media.get("shareCommentary", {}).get("text"):
        return text

    for key in ("text", "content", "description"):
        val = post.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, dict):
            if inner := val.get("text"):
                return inner

    return ""


def _extract_post_id(post: Dict[str, Any]) -> str:
    return post.get("id") or post.get("urn") or post.get("$URN", "unknown")


def _extract_published_at(post: Dict[str, Any]) -> Optional[str]:
    """Retorna la fecha de publicacion como string ISO-8601. Los timestamps de LinkedIn estan en ms."""
    ts = (
        post.get("publishedAt")
        or post.get("createdAt")
        or (post.get("created") or {}).get("time")
    )
    if ts is None:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(int(ts) / 1000, tz=datetime.timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return str(ts)


# Helpers: LLM chains

def _post_analysis_batch_chain(llm: Any) -> Any:
    """Cadena de una sola llamada: recibe todos los posts a la vez, retorna PostAnalysisBatch."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", _POST_ANALYSIS_SYSTEM),
        ("human", _POST_ANALYSIS_BATCH_HUMAN),
    ])
    return prompt | llm.with_structured_output(PostAnalysisBatch)


def _scrape_extraction_chain(llm: Any) -> Any:
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SCRAPE_EXTRACTION_SYSTEM),
        ("human", _SCRAPE_EXTRACTION_HUMAN),
    ])
    return prompt | llm.with_structured_output(ExtractedLinkedInData)


# Helpers: batch post analysis (1 LLM call for ALL posts)

def _build_posts_block(posts: List[Dict[str, Any]], max_posts: int) -> tuple[List[Dict], str]:
    """
    Construye el string formateado del bloque de posts para el prompt del lote.
    Retorna (valid_posts_metadata, posts_block_str).
    valid_posts_metadata: lista de {post_id, published_at} para posts con texto legible.
    """
    valid_posts = []
    lines = []

    for i, post in enumerate(posts[:max_posts], start=1):
        post_text = _extract_post_text(post)
        if not post_text or not post_text.strip():
            logger.debug("Post skipped (no readable text): %s", _extract_post_id(post))
            continue

        post_id = _extract_post_id(post)
        published_at = _extract_published_at(post) or ""
        truncated = post_text[:1500]  # slightly shorter per post to keep total prompt size manageable

        valid_posts.append({"post_id": post_id, "published_at": published_at})
        lines.append(
            f"POST {i}\n"
            f"---\n"
            f"id: {post_id}\n"
            f"date: {published_at}\n"
            f"text:\n{truncated}\n"
        )

    return valid_posts, "\n".join(lines)


def _analyze_posts_batch(
    posts: List[Dict[str, Any]],
    company_name: str,
    llm: Any,
    max_posts: int = 10,
    new_posts_only: bool = False,
    known_post_urns: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    Analiza hasta max_posts posts en UNA SOLA llamada LLM.

    Si new_posts_only=True, solo los posts cuyo id/urn NO esta en known_post_urns
    son enviados al LLM. Los posts sin texto legible siempre son descartados.
    Retorna [] inmediatamente si no quedan posts nuevos (no se hace llamada LLM).

    Usa _llm_invoke_with_retry para manejar 429/ResourceExhausted con retroceso exponencial.
    Cae a una lista vacia si la llamada LLM falla despues de todos los reintentos.
    """
    # Filter to new posts only if requested
    if new_posts_only and known_post_urns:
        posts = [p for p in posts if _extract_post_id(p) not in known_post_urns]
        logger.info(
            "[batch_analysis] new_posts_only=True: %d posts despues de filtrar URNs conocidos para '%s'.",
            len(posts), company_name,
        )
        if not posts:
            logger.info("[batch_analysis] No hay posts nuevos para analizar de '%s'. Omitiendo llamada LLM.", company_name)
            return []

    valid_posts, posts_block = _build_posts_block(posts, max_posts)

    if not valid_posts:
        logger.info("No se encontraron posts con texto legible para '%s'.", company_name)
        return []

    n = len(valid_posts)
    logger.info(
        "[batch_analysis] Enviando %d posts al LLM en una sola llamada para '%s'.",
        n, company_name,
    )

    chain = _post_analysis_batch_chain(llm)
    try:
        result: PostAnalysisBatch = _llm_invoke_with_retry(chain, {
            "n": n,
            "company_name": company_name,
            "posts_block": posts_block,
        })
        analyses = [a.model_dump() for a in result.analyses]
        logger.info(
            "[batch_analysis] Completado: %d/%d posts analizados para '%s'.",
            len(analyses), n, company_name,
        )
        return analyses
    except Exception as exc:
        logger.warning(
            "[batch_analysis] Llamada LLM por lotes fallo para '%s': %s. "
            "Retornando analisis vacio.",
            company_name, exc,
        )
        return []


# Helpers: public page scraping

def _scrape_and_extract(vanity_name: str, llm: Any) -> Optional[ExtractedLinkedInData]:
    """
    Raspa la pagina publica de empresa de LinkedIn y extrae datos estructurados.
    Retorna None elegantemente en cualquier fallo de HTTP o parseo.
    Usa _llm_invoke_with_retry para manejar 429/ResourceExhausted con retroceso exponencial.
    """
    url = f"https://www.linkedin.com/company/{vanity_name}"
    logger.info("Raspando la pagina publica de LinkedIn: %s", url)

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        raw_text = " ".join(soup.get_text(separator=" ", strip=True).split())
        if len(raw_text) < 100:
            logger.warning("El raspado de %s retorno texto insuficiente (<100 chars).", url)
            return None

        scraped_content = raw_text[:6000]

    except requests.RequestException as exc:
        logger.warning("Error HTTP raspando %s: %s", url, exc)
        return None
    except Exception as exc:
        logger.warning("Error inesperado raspando %s: %s", url, exc)
        return None

    try:
        chain = _scrape_extraction_chain(llm)
        extracted: ExtractedLinkedInData = _llm_invoke_with_retry(
            chain, {"scraped_content": scraped_content}
        )
        logger.info("Extraccion de pagina publica completada para '%s'.", vanity_name)
        return extracted
    except Exception as exc:
        logger.warning("La extraccion LLM fallo para '%s': %s", vanity_name, exc)
        return None


# Helpers: data merging

def _merge_org_details(profile: Dict[str, Any], org: Optional[Dict[str, Any]]) -> None:
    """
    Enriquece el perfil con org_details de la API de LinkedIn.
    Solo rellena los campos que actualmente son None — nunca sobrescribe datos existentes.
    """
    if not org or not isinstance(org, dict):
        return

    field_map = {
        "localizedName": "name",
        "industries": "industry",
        "staffCount": "company_size",
        "headquartersCity": "headquarters",
        "companyType": "company_type",
        "foundedOn": "founded",
        "specialties": "specialties",
        "followerCount": "followers",
    }

    for api_key, profile_key in field_map.items():
        if profile.get(profile_key):
            continue
        value = org.get(api_key)
        if value is None:
            continue
        if isinstance(value, list):
            profile[profile_key] = value
        elif isinstance(value, (int, float)):
            profile[profile_key] = str(value)
        else:
            profile[profile_key] = str(value)


def _merge_scraped(profile: Dict[str, Any], scraped: Optional[ExtractedLinkedInData]) -> None:
    """Rellena los campos vacios restantes de los datos raspados (fuente de menor prioridad)."""
    if not scraped:
        return
    for field in ("followers", "industry", "company_size", "headquarters", "company_type", "founded"):
        if not profile.get(field) and getattr(scraped, field, None):
            profile[field] = getattr(scraped, field)
    if not profile.get("specialties") and scraped.specialties:
        profile["specialties"] = scraped.specialties
    if not profile.get("about_us_content") and scraped.about_us:
        profile["about_us_content"] = scraped.about_us


# Main node

def run_company_profiler_node(
    state: AgentState,
    new_posts_only: bool = False,
    known_post_urns: Optional[set] = None,
) -> Dict[str, Any]:
    """
    Nodo de LangGraph: construye un CompanyProfile completo con persistencia incremental en Supabase.

    Pipeline:
      1. Validar inputs del estado.
      2. Llamada batch a la API de LinkedIn -> org_details, posts crudos, conteo de seguidores.
      3. [FASE A] Si se proporciona el callable save_company_profile en el estado, persistir el perfil base
         inmediatamente (recent_posts_analysis=[]) para que los datos no se pierdan si el LLM falla.
         posts_stored_count = posts ya en BD antes de esta ejecucion (de existing_company_profile).
      4. Analizar todos los posts con UNA SOLA llamada batch LLM -> List[PostAnalysis].
         Si new_posts_only=True, solo los posts no en known_post_urns se envian al LLM.
      5. Raspar pagina publica de LinkedIn -> fallback/datos de enriquecimiento.
      6. Fusionar todas las fuentes (API > scrape > session) en CompanyProfile.
      7. [FASE B] Si se proporciona el callable save_company_profile, actualizar registro con analisis completo.
         posts_stored_count = len(merged) cuando new_posts_only, sino len(posts_analysis).
         Si new_posts_only=True, los nuevos analisis se fusionan con los almacenados existentes (limite 30).

    La clave de estado 'save_profile_fn' es opcional. Si esta presente debe ser un callable:
        save_profile_fn(org_urn, org_name, raw_batch_data, company_profile_data, follower_count)
    Esto permite a la tarea Celery inyectar su propia funcion de persistencia sin
    acoplar este nodo directamente a Supabase.

    Args:
        state: Dict del estado del agente LangGraph.
        new_posts_only: Cuando es True, solo los posts no presentes en known_post_urns son analizados.
        known_post_urns: Set de URNs/IDs de posts ya analizados para omitir. Usado con new_posts_only.
    """
    logger.info("=== COMPANY PROFILER: start ===")

    # 1. Validate inputs
    selected_account = state.get("selected_account")
    if not selected_account:
        raise ValueError("'selected_account' is required in state.")

    vanity_name: Optional[str] = selected_account.get("vanityName")
    if not vanity_name:
        raise ValueError("'vanityName' is required in selected_account.")

    org_urn: Optional[str] = selected_account.get("urn")
    company_name: str = selected_account.get("name") or vanity_name

    access_token: Optional[str] = state.get("linkedin_access_token")
    if not access_token:
        raise ValueError("'linkedin_access_token' is required in state.")

    # Optional persistence hook injected by the Celery task
    save_profile_fn = state.get("save_profile_fn")  # callable or None
    # Refresh mode: when True, only new posts (not in known_post_urns) are sent to LLM.
    # The caller (company_batch_refresh_task) is responsible for populating known_post_urns.
    _known_urns: set = known_post_urns or set()

    # Existing profile from DB — used to compute posts_stored_count for FASE A
    # and to merge analyses in FASE B (new_posts_only mode).
    existing_profile: Dict[str, Any] = state.get("existing_company_profile") or {}
    existing_analyses: List[Dict[str, Any]] = (
        (existing_profile.get("company_profile") or {}).get("recent_posts_analysis") or []
    )
    # posts_stored_count for FASE A = total posts already in DB before this run.
    # This is the count from the last successful save, not the count of the current API batch.
    _db_posts_stored_count: int = existing_profile.get("posts_stored_count") or len(existing_analyses)

    # 2. LinkedIn batch API
    # Si tasks.py ya hizo la extraccion paginada e inyecto raw_batch_data en el state,
    # lo reutilizamos directamente para evitar una segunda llamada a la API de LinkedIn
    # (que ademas solo devolveria los primeros 20 posts, perdiendo la paginacion).
    injected_batch = state.get("raw_batch_data")
    if injected_batch:
        logger.info(
            "Reutilizando raw_batch_data inyectado por tasks.py para URN: %s (%d posts)",
            org_urn, len(injected_batch.get("posts") or []),
        )
        batch = injected_batch
    elif org_urn:
        logger.info("Obteniendo batch data de LinkedIn para el URN: %s", org_urn)
        try:
            batch = get_linkedin_company_batch_data(
                access_token=access_token,
                org_urn=org_urn,
                posts_count=20,
            )
        except Exception as exc:
            logger.error("API Batch fallo para %s: %s — continuando con datos vacios.", org_urn, exc)
            batch = {"organization": None, "posts": [], "follower_count": None}
    else:
        logger.warning("No hay org_urn disponible; omitiendo llamada a API batch.")
        batch = {"organization": None, "posts": [], "follower_count": None}

    org_details: Optional[Dict[str, Any]] = batch.get("organization")
    raw_posts: List[Dict[str, Any]] = batch.get("posts") or []
    api_followers: Optional[int] = batch.get("follower_count")

    logger.info(
        "Batch API finalizado: org=%s, posts=%d, followers=%s",
        "OK" if org_details else "None", len(raw_posts), api_followers,
    )

    # Build base profile dict (no LLM data yet)
    profile_dict: Dict[str, Any] = {
        "name": company_name,
        "urn": org_urn,
        "vanity_name": vanity_name,
        "followers": str(api_followers) if api_followers is not None else None,
        "industry": None,
        "company_size": None,
        "headquarters": None,
        "company_type": None,
        "founded": None,
        "specialties": None,
        "about_us_content": None,
        "recent_posts_analysis": [],
    }
    _merge_org_details(profile_dict, org_details)

    # 3. FASE A — persist base profile immediately so data survives LLM failures.
    # posts_stored_count = posts already in DB BEFORE this run (not the current API batch).
    # This lets the next run know how many posts were stored last time and detect deltas.
    if callable(save_profile_fn):
        try:
            logger.info(
                "[FASE A] Upsert base profile para '%s' (sin analisis LLM). "
                "db_posts_stored=%d, api_posts_now=%d.",
                company_name, _db_posts_stored_count, len(raw_posts),
            )
            save_profile_fn(
                org_urn=org_urn,
                org_name=company_name,
                raw_batch_data=batch,
                company_profile_data=dict(profile_dict),
                follower_count=api_followers,
                posts_stored_count=_db_posts_stored_count,
                posts_analyzed_count=len(existing_analyses),
                total_posts_available=len(raw_posts) if raw_posts else 0,
            )
            logger.info("[FASE A] Upsert completado para '%s'.", company_name)
        except Exception as exc:
            # Non-fatal: log and continue — LLM analysis is more important
            logger.warning("[FASE A] Upsert base fallido para '%s': %s", company_name, exc)

    # 4. Batch post analysis — analiza TODOS los posts extraidos.
    # Se procesan en lotes de BATCH_SIZE para evitar prompts excesivamente largos
    # y respetar el limite de tokens del modelo.
    analysis_llm = ChatGoogleGenerativeAI(model=ANALYSIS_LLM, google_api_key=GENAI_API_KEY, temperature=0.1)
    posts_analysis: List[Dict[str, Any]] = []
    BATCH_SIZE = 20  # posts por llamada LLM; ajustar segun limite de tokens del modelo

    if raw_posts:
        total_posts = len(raw_posts)
        logger.info(
            "[batch_analysis] Analizando %d posts en lotes de %d para '%s'...",
            total_posts, BATCH_SIZE, company_name,
        )
        for batch_start in range(0, total_posts, BATCH_SIZE):
            batch_slice = raw_posts[batch_start: batch_start + BATCH_SIZE]
            logger.info(
                "[batch_analysis] Lote %d-%d de %d para '%s'.",
                batch_start + 1, batch_start + len(batch_slice), total_posts, company_name,
            )
            batch_result = _analyze_posts_batch(
                batch_slice, company_name, analysis_llm,
                max_posts=BATCH_SIZE,
                new_posts_only=new_posts_only,
                known_post_urns=_known_urns,
            )
            posts_analysis.extend(batch_result)
        logger.info(
            "[batch_analysis] Total: %d/%d posts analizados para '%s'.",
            len(posts_analysis), total_posts, company_name,
        )
    else:
        logger.info("No hay posts para analizar.")

    # 5. Public page scraping (enrichment / fallback)
    medium_llm = ChatGoogleGenerativeAI(model=MEDIUM_LLM, google_api_key=GENAI_API_KEY, temperature=0.0)
    scraped_data = _scrape_and_extract(vanity_name, medium_llm)

    # 6. Merge: API > scrape > session defaults
    profile_dict["recent_posts_analysis"] = posts_analysis
    _merge_scraped(profile_dict, scraped_data)

    # Consolidación final del state previa al upsert de Fase B

    # 7. FASE B — update record with full analysis.
    # posts_stored_count = total deduplicated posts after merge (new_posts_only)
    #                    = len(posts_analysis) for a fresh first extraction.
    # This is the authoritative count of posts now in DB so the next run
    # can compare against LinkedIn and detect new posts cheaply.
    if new_posts_only and posts_analysis:
        # Merge new analyses with existing stored ones: new first, deduplicate, cap at 30.
        seen_ids: set = set()
        merged: List[Dict[str, Any]] = []
        for entry in posts_analysis + existing_analyses:
            pid = entry.get("post_id", "")
            if pid not in seen_ids:
                seen_ids.add(pid)
                merged.append(entry)
            if len(merged) >= 30:
                break
        profile_dict["recent_posts_analysis"] = merged
        posts_analysis = merged
        logger.info(
            "[FASE B] Se fusionaron %d analisis nuevos + existentes -> %d total para '%s'.",
            len(posts_analysis), len(merged), company_name,
        )

    # Instanciación estructurada posterior al merge para asegurar consistencia del grafo
    profile = CompanyProfile(**profile_dict)  # type: ignore[arg-type]

    # posts_stored_count for FASE B:
    #   new_posts_only -> len(posts_analysis) = merged total (new + existing, deduped, capped 30)
    #   first extraction -> len(posts_analysis) = posts analysed this run
    # In both cases len(posts_analysis) is the correct total now stored in DB.
    _fase_b_posts_stored = len(posts_analysis)

    if callable(save_profile_fn):
        try:
            logger.info(
                "[FASE B] Upsert perfil completo para '%s' "
                "(posts_stored=%d, posts_analyzed=%d).",
                company_name, _fase_b_posts_stored, len(posts_analysis),
            )
            save_profile_fn(
                org_urn=org_urn,
                org_name=company_name,
                raw_batch_data=batch,
                company_profile_data=dict(profile_dict),
                follower_count=api_followers,
                posts_stored_count=_fase_b_posts_stored,
                posts_analyzed_count=len(posts_analysis),
                total_posts_available=len(raw_posts) if raw_posts else 0,
            )
            logger.info("[FASE B] Upsert completo para '%s'.", company_name)
        except Exception as exc:
            logger.warning("[FASE B] Upsert final fallido para '%s': %s", company_name, exc)

    logger.info(
        "=== COMPANY PROFILER: finalizado para '%s' | posts analizados: %d ===",
        profile["name"], len(posts_analysis),
    )
    return {"company_profile": profile}
