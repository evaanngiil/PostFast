"""
Juez LLM ciego para la evaluación comparativa (pairwise, aleatorizado).

Metodología anti-sesgo:
- El juez usa un modelo DISTINTO al generador (JUDGE_LLM) para mitigar la
  auto-preferencia.
- Comparación por pares con orden A/B aleatorizado por caso (mitiga el sesgo
  de posición) y sin revelar qué sistema produjo cada texto.
- Rúbrica cerrada de 5 dimensiones puntuadas 1-5 + veredicto global.
"""
import random
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.core.constants import JUDGE_LLM, GENAI_API_KEY
from src.core.logger import logger


class DimensionScores(BaseModel):
    brand_fidelity: int = Field(description="1-5: fidelidad a la identidad, productos y tono reales de la empresa descrita en el contexto.")
    factual_grounding: int = Field(description="1-5: ausencia de datos que suenen inventados; anclaje en información del contexto.")
    linkedin_craft: int = Field(description="1-5: calidad del hook, estructura escaneable, CTA y hashtags adecuados a LinkedIn.")
    originality: int = Field(description="1-5: aporta un ángulo propio, no suena a plantilla genérica de IA.")
    strategic_value: int = Field(description="1-5: probabilidad de generar engagement y valor de negocio para la empresa.")


class PairVerdict(BaseModel):
    scores_a: DimensionScores = Field(description="Puntuaciones del Post A.")
    scores_b: DimensionScores = Field(description="Puntuaciones del Post B.")
    winner: str = Field(description="'A', 'B' o 'TIE' según cuál publicarías como responsable de la marca.")
    rationale: str = Field(description="Justificación breve (2-3 frases) del veredicto.")


JUDGE_PROMPT = """Eres un Director de Marketing y Comunicación senior evaluando a ciegas dos borradores de post de LinkedIn para tu empresa. No sabes qué herramienta produjo cada uno.

**Contexto real de la empresa (resumen; la base de conocimientos completa es más amplia):**
{company_context}

**Petición original:**
"{prompt}"

**Post A:**
---
{post_a}
---

**Post B:**
---
{post_b}
---

**Auditoría factual independiente (mismo auditor para ambos posts; verificación claim-por-claim contra la base de conocimientos COMPLETA de la empresa y fuentes web):**
- Post A: {audit_a}
- Post B: {audit_b}

**Instrucciones de evaluación:**
1. Para la dimensión `factual_grounding`, la auditoría factual es tu evidencia PRINCIPAL: no marques como inventado un dato que la auditoría verificó (el contexto de arriba es solo un resumen parcial), y penaliza con dureza las afirmaciones que la auditoría señala SIN evidencia.
2. Penaliza superlativos indemostrables, placeholders sin rellenar y contenido genérico intercambiable entre empresas.
3. Evalúa AMBOS posts con la rúbrica (1=muy deficiente, 5=excelente) y decide cuál publicarías.

Responde en el formato estructurado solicitado.
"""


def judge_pair(
    prompt: str,
    output_1: str,
    output_2: str,
    company_context: str,
    system_1: str,
    system_2: str,
    rng: random.Random | None = None,
    audit_1: str = "No disponible.",
    audit_2: str = "No disponible.",
) -> Dict[str, Any]:
    """
    Compara dos salidas a ciegas con orden aleatorizado.

    :param audit_1/audit_2: resumen de la auditoría factual objetiva de cada
           salida (simétrica: el mismo auditor CRAG evalúa ambas).
    :returns: Dict con winner_system (nombre real del sistema ganador o 'TIE'),
              puntuaciones por dimensión mapeadas a cada sistema y la justificación.
    """
    rng = rng or random.Random()
    flipped = rng.random() < 0.5
    post_a, post_b = (output_2, output_1) if flipped else (output_1, output_2)
    sys_a, sys_b = (system_2, system_1) if flipped else (system_1, system_2)
    audit_a, audit_b = (audit_2, audit_1) if flipped else (audit_1, audit_2)

    llm = ChatGoogleGenerativeAI(model=JUDGE_LLM, google_api_key=GENAI_API_KEY, temperature=0.0)
    structured = llm.with_structured_output(PairVerdict)

    try:
        verdict = structured.invoke(JUDGE_PROMPT.format(
            company_context=company_context[:10000],
            prompt=prompt,
            post_a=post_a[:4000],
            post_b=post_b[:4000],
            audit_a=audit_a,
            audit_b=audit_b,
        ))
    except Exception as exc:
        logger.error("[judge] Fallo del juez LLM: %s", exc)
        return {"error": str(exc)}

    winner_letter = verdict.winner.strip().upper()
    if winner_letter == "A":
        winner_system = sys_a
    elif winner_letter == "B":
        winner_system = sys_b
    else:
        winner_system = "TIE"

    return {
        "winner_system": winner_system,
        "flipped": flipped,
        "scores": {
            sys_a: verdict.scores_a.model_dump(),
            sys_b: verdict.scores_b.model_dump(),
        },
        "rationale": verdict.rationale,
        "judge_model": JUDGE_LLM,
    }
