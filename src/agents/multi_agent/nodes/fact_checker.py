"""
Nodo Fact Checker (CRAG) para PostFast.

Implementa verificación factual en tres etapas (Corrective RAG real):
1. EXTRACCIÓN: identifica los claims verificables del borrador y los clasifica
   como internos (sobre la empresa/productos) o externos (estadísticas del sector).
2. EVIDENCIA: recupera evidencia específica POR CLAIM — RAG corporativo para
   claims internos y búsqueda web para claims externos.
3. VEREDICTO: evalúa cada claim contra su propia evidencia y emite el reporte.

Si un claim no está respaldado por evidencia, el supervisor devuelve el control
al Content Writer con las correcciones propuestas (bucle de auto-corrección).
"""
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.multi_agent.state import AgentState
from src.agents.multi_agent.utils import parse_post_text
from src.services.rag_service import search_knowledge
from src.agents.multi_agent.tools.profiler_tools import web_search
from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
from src.core.logger import logger

# Máximo de claims a verificar por pasada (control de coste/cuota).
MAX_CLAIMS = 6

# Reescrituras completas del writer permitidas antes del aterrizaje seguro.
MAX_REWRITE_LOOPS = 2


class ExtractedClaim(BaseModel):
    claim: str = Field(description="Afirmación factual verificable extraída del borrador (dato, métrica, hito, característica de producto).")
    claim_type: str = Field(
        description="'internal' si trata sobre la empresa, sus productos o servicios; 'external' si es un dato del sector, estadística de mercado o hecho del mundo real."
    )


class ClaimExtraction(BaseModel):
    claims: List[ExtractedClaim] = Field(
        default_factory=list,
        description="Claims factuales del post. Vacío si el post solo contiene opiniones, saludos o contenido subjetivo.",
    )


class FactClaim(BaseModel):
    claim: str = Field(description="El claim factual extraído del borrador del post (estadísticas, hitos, datos concretos).")
    verified: bool = Field(description="True si el claim pudo ser corroborado con las fuentes, False si es dudoso o inventado.")
    source: str = Field(description="Nombre o identificador de la fuente ('brand_book', 'product_catalog', 'web:...', etc.) o 'no_source_found'.")
    correction: str = Field(
        default="",
        description="Propuesta de corrección basada en la evidencia si el claim es incorrecto o impreciso."
    )


class FactCheckReport(BaseModel):
    claims: List[FactClaim] = Field(description="Lista de claims de datos analizados en el post.")
    overall_pass: bool = Field(
        description="True si todos los claims son verídicos o el post no contiene claims factuales que requieran corrección."
    )
    summary: str = Field(description="Resumen del proceso de verificación de hechos.")


EXTRACTION_PROMPT = """Eres un auditor factual. Extrae del siguiente borrador de post de LinkedIn los claims factuales VERIFICABLES (datos, cifras, estadísticas, hitos, características de producto, afirmaciones sobre capacidades).

NO extraigas opiniones, saludos, preguntas retóricas ni frases motivacionales.
Clasifica cada claim:
- 'internal': afirma algo sobre la empresa "{company_name}", sus productos, servicios o logros.
- 'external': afirma algo sobre el mercado, el sector, estadísticas globales o hechos del mundo.

Extrae como máximo {max_claims} claims (los más relevantes/arriesgados primero).

**Borrador:**
{draft_content}
"""

VERDICT_PROMPT = """Eres un Verificador de Hechos corporativo y riguroso de la empresa "{company_name}".
Se ha recuperado evidencia específica para cada claim del borrador. Evalúa cada claim EXCLUSIVAMENTE contra su propia evidencia.

**Reglas del veredicto:**
1. `verified = True` solo si la evidencia respalda razonablemente el claim.
2. `verified = False` si la evidencia lo contradice O si no existe evidencia alguna que lo respalde (posible alucinación). En ese caso, propone una `correction` fiel a la evidencia disponible (o sugiere eliminar el dato si no hay sustituto verídico).
3. En `source` indica de dónde proviene la evidencia que usaste ('brand_book', 'product_catalog', 'pdf_document', 'web:<dominio>', etc.) o 'no_source_found'.
4. No penalices opiniones ni estilo: solo hechos.

**Claims con su evidencia:**
{claims_with_evidence}

Genera el reporte de verificación detallado en el formato estructurado solicitado.
"""

SAFE_LANDING_PROMPT = """Eres un editor de compliance factual. El siguiente post de LinkedIn contiene afirmaciones SIN EVIDENCIA que deben eliminarse antes de publicar.

**Post actual:**
---
{draft_content}
---

**Afirmaciones sin evidencia que DEBES eliminar o generalizar (sin cifras ni nombres concretos):**
{claims_to_remove}

**Reglas estrictas:**
1. ELIMINA cada afirmación listada, o generalízala sin datos concretos (ej. "ahorros de hasta un 40%" -> "ahorros significativos") SOLO si la frase es imprescindible para la coherencia.
2. ABSOLUTAMENTE PROHIBIDO añadir datos, cifras, nombres, productos o ejemplos nuevos.
3. Conserva intactos el resto del texto, su formato, saltos de línea, emojis y hashtags.
4. Devuelve ÚNICAMENTE el texto final del post, sin comentarios ni preámbulos.
"""


def _safe_landing(draft_content: str, unverified_claims: list, report_dict: dict, llm) -> Dict[str, Any]:
    """
    Aterrizaje seguro: agotado el presupuesto de reescrituras, elimina del post
    los claims sin evidencia en una única edición dirigida. Garantiza que ningún
    dato no verificado llegue al usuario (en lugar del fail-open anterior).
    """
    claims_text = "\n".join(
        f"- \"{c.get('claim')}\"" + (f" (corrección sugerida: {c.get('correction')})" if c.get("correction") else "")
        for c in unverified_claims
    )
    logger.warning(
        "Fact checker: presupuesto de reescrituras agotado. Aterrizaje seguro: "
        "eliminando %d claims sin evidencia del borrador.", len(unverified_claims),
    )
    try:
        raw = llm.invoke(SAFE_LANDING_PROMPT.format(
            draft_content=draft_content,
            claims_to_remove=claims_text,
        )).content
        if isinstance(raw, list):
            raw = "\n".join(p if isinstance(p, str) else p.get("text", str(p)) for p in raw)
        new_draft = parse_post_text(raw)
        if not new_draft.get("content"):
            raise ValueError("El aterrizaje seguro devolvió un post vacío.")

        report_dict["overall_pass"] = True
        report_dict["evaluated"] = True
        report_dict["claims_removed"] = [c.get("claim") for c in unverified_claims]
        report_dict["summary"] = (
            f"Aterrizaje seguro: {len(unverified_claims)} claims sin evidencia fueron "
            "eliminados del post tras agotar el presupuesto de reescrituras."
        )
        return {"draft_post": new_draft, "fact_check_report": report_dict}
    except Exception as exc:
        logger.error(f"Fact checker: fallo en el aterrizaje seguro: {exc}")
        # Último recurso: pasa marcado como NO evaluado (visible en UI/informe).
        report_dict["overall_pass"] = True
        report_dict["evaluated"] = False
        report_dict["summary"] = f"Aterrizaje seguro fallido ({exc}); post no verificado."
        return {"fact_check_report": report_dict}


def _gather_evidence(claim: ExtractedClaim, org_urn: str, link_url: str | None = None) -> str:
    """Recupera evidencia específica para un claim según su tipo."""
    evidence_parts = []

    # Si hay una URL de referencia provista, intentamos buscar fragmentos de esa URL como evidencia prioritaria.
    if org_urn and link_url:
        try:
            from src.services.supabase_client import get_supabase_admin
            sb = get_supabase_admin()
            res = sb.table("company_knowledge").select("content").eq("org_urn", org_urn).eq("source_type", "web_page").like("source_id", f"{link_url}%").execute()
            rows = res.data or []
            if rows:
                url_evidence = "\n".join(f"[web_page_reference] {row.get('content')[:600]}" for row in rows[:3])
                evidence_parts.append(url_evidence)
                logger.info(f"Fact checker: inyectados {len(rows[:3])} chunks de la URL de referencia como evidencia.")
        except Exception as exc:
            logger.warning(f"Fact checker: error recuperando URL de referencia como evidencia: {exc}")

    # Claims internos: base de conocimientos corporativa (RAG).
    if org_urn:
        try:
            rag_hits = search_knowledge(
                query=claim.claim,
                org_urn=org_urn,
                threshold=0.4,
                limit=3,
            )
            for hit in rag_hits:
                evidence_parts.append(f"[{hit.get('source_type', 'kb')}] {hit.get('content', '')[:600]}")
        except Exception as exc:
            logger.warning(f"Fact checker: error recuperando RAG para claim '{claim.claim[:60]}': {exc}")

    # Claims externos: contrastar además contra la web.
    if claim.claim_type == "external":
        try:
            web_result = web_search.invoke({"query": claim.claim})
            if web_result and "not available" not in web_result:
                evidence_parts.append(f"[web_search] {web_result[:1200]}")
        except Exception as exc:
            logger.warning(f"Fact checker: error en web_search para claim '{claim.claim[:60]}': {exc}")

    return "\n".join(evidence_parts) if evidence_parts else "SIN EVIDENCIA ENCONTRADA."


def run_fact_checker_node(state: AgentState) -> Dict[str, Any]:
    logger.info("=== FACT CHECKER (CRAG): start ===")

    task_id = state.get("task_id")
    if task_id:
        from src.services.realtime_service import broadcast_task_status_sync
        broadcast_task_status_sync(task_id, "RUNNING", {
            "node": "Fact Checker",
            "message": "Extrayendo claims del post y verificándolos contra la evidencia (RAG + web)..."
        })

    draft_post = state.get("draft_post", {})
    draft_content = draft_post.get("content", "") if draft_post else ""
    company_profile = state.get("company_profile", {})
    org_urn = company_profile.get("urn", "")
    company_name = company_profile.get("name", "la empresa")
    loops = state.get("correction_loops") or 0

    if loops >= 4:
        # Backstop de emergencia (no debería alcanzarse: el aterrizaje seguro
        # actúa antes). Se mantiene para blindar contra bucles infinitos.
        logger.warning(f"Fact checker: superado límite absoluto de reintentos ({loops}). Forzando aprobación.")
        return {
            "fact_check_report": {
                "claims": [],
                "overall_pass": True,
                "evaluated": False,
                "summary": "Verificación de hechos omitida por límite de reintentos alcanzado.",
            }
        }

    if not draft_content:
        logger.warning("Fact checker: no hay borrador de post para verificar.")
        return {
            "fact_check_report": {
                "claims": [],
                "overall_pass": True,
                "evaluated": False,
                "summary": "Sin borrador para analizar factualidad.",
            }
        }

    llm = ChatGoogleGenerativeAI(
        model=MEDIUM_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=0.0,  # Máxima precisión, libre de alucinaciones
    )

    try:
        # ---- ETAPA 1: extracción y clasificación de claims ----
        extraction_chain = (
            ChatPromptTemplate.from_template(EXTRACTION_PROMPT)
            | llm.with_structured_output(ClaimExtraction)
        )
        extraction = extraction_chain.invoke({
            "company_name": company_name,
            "max_claims": MAX_CLAIMS,
            "draft_content": draft_content,
        })
        claims = (extraction.claims if extraction else [])[:MAX_CLAIMS]

        if not claims:
            logger.info("=== FACT CHECKER: sin claims verificables, aprobado ===")
            return {
                "fact_check_report": {
                    "claims": [],
                    "overall_pass": True,
                    "evaluated": True,
                    "summary": "El post no contiene claims factuales verificables; nada que corregir.",
                }
            }

        logger.info(
            "Fact checker: %d claims extraídos (%d internos / %d externos).",
            len(claims),
            sum(1 for c in claims if c.claim_type == "internal"),
            sum(1 for c in claims if c.claim_type == "external"),
        )

        # ---- ETAPA 2: recuperación de evidencia POR CLAIM ----
        claims_with_evidence = []
        for i, claim in enumerate(claims, 1):
            evidence = _gather_evidence(claim, org_urn, state.get("link_url"))
            claims_with_evidence.append(
                f"### Claim {i} ({claim.claim_type}):\n\"{claim.claim}\"\n**Evidencia recuperada:**\n{evidence}\n"
            )

        # ---- ETAPA 3: veredicto por claim contra su evidencia ----
        verdict_chain = (
            ChatPromptTemplate.from_template(VERDICT_PROMPT)
            | llm.with_structured_output(FactCheckReport)
        )
        report = verdict_chain.invoke({
            "company_name": company_name,
            "claims_with_evidence": "\n".join(claims_with_evidence),
        })

        report_dict = report.model_dump() if hasattr(report, "model_dump") else dict(report)
        report_dict["evaluated"] = True

        unverified_claims = [c for c in report_dict.get("claims", []) if not c.get("verified")]

        if unverified_claims:
            # Presupuesto de reescrituras agotado -> aterrizaje seguro:
            # se eliminan los claims sin evidencia en vez de re-generar (evita
            # la oscilación de claims nuevos) o de dejar pasar sin verificar.
            if loops >= MAX_REWRITE_LOOPS:
                return _safe_landing(draft_content, unverified_claims, report_dict, llm)

            report_dict["overall_pass"] = False
            logger.info(
                "❌ FACT CHECKER: %d claims dudosos o alucinados de %d analizados.",
                len(unverified_claims), len(report_dict.get("claims", [])),
            )
            return {"fact_check_report": report_dict, "correction_loops": loops + 1}

        report_dict["overall_pass"] = True
        logger.info(
            "✅ FACT CHECKER: aprobado (%d claims verificados contra evidencia).",
            len(report_dict.get("claims", [])),
        )
        return {"fact_check_report": report_dict}

    except Exception as e:
        logger.error(f"Fallo en la ejecución del Fact Checker: {e}")
        # Fail-open documentado: ante error técnico del servicio LLM no se congela
        # la cola, pero el reporte queda marcado como NO evaluado para que la UI
        # pueda distinguir 'aprobado' de 'no verificado'.
        return {
            "fact_check_report": {
                "claims": [],
                "overall_pass": True,
                "evaluated": False,
                "summary": f"Verificación de hechos omitida por error técnico: {e}",
            }
        }
