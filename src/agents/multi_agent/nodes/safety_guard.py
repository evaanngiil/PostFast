"""
Nodo Safety Guard para PostFast.
Evalúa que el borrador del post cumpla con las políticas internas de la marca,
pautas de comunicación de LinkedIn, cumplimiento de GDPR y no contenga temas
prohibidos o menciones dañinas a competidores.
"""
from typing import Dict, Any, List
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.multi_agent.state import AgentState
from src.services.rag_service import search_knowledge
from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
from src.core.logger import logger

class SafetyReport(BaseModel):
    approved: bool = Field(description="True si el post cumple rigurosamente con todas las políticas de marca y compliance.")
    issues: List[str] = Field(
        default_factory=list,
        description="Lista de faltas u ofensas encontradas (vacía si aprobado es True)."
    )
    severity: str = Field(
        default="none",
        description="Gravedad de la falta: 'none', 'low', 'medium', 'high', 'critical'."
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Sugerencias constructivas para ajustar el post a la política de marca."
    )

SAFETY_PROMPT = """Eres el Revisor de Compliance de Marca y Seguridad de {company_name}. Tu misión es auditar el borrador de post para LinkedIn contra nuestras políticas corporativas y legales.

**Borrador de la Publicación:**
{draft_content}

**Pautas del Perfil de Marca (Brand Persona):**
{brand_persona}

**Guías de Marca de la Base de Conocimientos (RAG Context):**
{brand_guidelines_context}

**Políticas Corporativas (su incumplimiento constituye una INFRACCIÓN):**
1. **Temas Prohibidos**: opinar o hacer mención a política, religión, contenidos de odio, drogas o lenguaje difamatorio.
2. **GDPR e Identidad**: citar nombres de clientes, partners o empleados sin autorización explícita declarada; exponer datos financieros o privados.
3. **Competidores**: difamar, comparar de forma despectiva o mencionar explícitamente a competidores de la industria.
4. **Autenticidad**: superlativos no demostrables ("el mejor del mercado", "100% infalible", "único en el mundo") que constituyan publicidad engañosa.
5. **Tono gravemente desalineado**: contenido soberbio, agresivo u ofensivo incompatible con el Perfil de Marca.

**CALIBRACIÓN DEL VEREDICTO (importante):**
- `approved = false` SOLO si existe al menos una infracción REAL de las políticas 1-5. En ese caso, `severity` refleja la más grave: 'medium' (corregible), 'high' o 'critical' (inaceptable).
- Las observaciones de estilo, formato, longitud, número de emojis o mejoras deseables NO son infracciones: van en `suggestions`, con `approved = true` y `severity` 'none' o 'low'.
- Un post normal de marketing profesional sin infracciones debe salir `approved = true`. No busques problemas donde no los hay: los falsos positivos bloquean el pipeline sin motivo.

Analiza el borrador del post y genera el reporte de seguridad en el formato JSON estructurado solicitado.
"""

def run_safety_guard_node(state: AgentState) -> Dict[str, Any]:
    logger.info("=== SAFETY GUARD: start ===")

    task_id = state.get("task_id")
    if task_id:
        from src.services.realtime_service import broadcast_task_status_sync
        broadcast_task_status_sync(task_id, "RUNNING", {
            "node": "Safety Guard",
            "message": "Comprobando cumplimiento de políticas de marca y compliance de la publicación..."
        })
    
    draft_post = state.get("draft_post", {})
    draft_content = draft_post.get("content", "") if draft_post else ""
    persona = state.get("brand_persona_json", {})
    company_profile = state.get("company_profile", {})
    org_urn = company_profile.get("urn", "")
    company_name = company_profile.get("name", "Empresa")
    loops = state.get("correction_loops") or 0
    
    if loops >= 3:
        logger.warning(f"Safety Guard: superado límite de reintentos ({loops}). Forzando aprobación para evitar bucle infinito.")
        return {
            "safety_report": {
                "approved": True,
                "evaluated": False,
                "issues": [],
                "severity": "none",
                "suggestions": ["Revisión de seguridad omitida por límite de reintentos alcanzado."]
            }
        }

    if not draft_content:
        logger.warning("Safety Guard: no hay borrador de post para auditar.")
        return {
            "safety_report": {
                "approved": True,
                "evaluated": False,
                "issues": [],
                "severity": "none",
                "suggestions": ["Sin borrador para analizar."]
            }
        }
        
    # Obtener guías de estilo específicas del RAG
    brand_guidelines = ""
    if org_urn:
        guidelines = search_knowledge(
            query="guía de tono de voz, políticas de comunicación corporativa y do's y don'ts",
            org_urn=org_urn,
            source_type="brand_book",
            threshold=0.55,
            limit=3
        )
        if guidelines:
            brand_guidelines = "\n**Pautas del Brand Book recuperadas de RAG:**\n" + "\n".join(
                f"- {g['content']}" for g in guidelines
            )
            
    llm = ChatGoogleGenerativeAI(
        model=MEDIUM_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=0.0  # Absoluto determinismo para auditoría
    )
    structured_llm = llm.with_structured_output(SafetyReport)
    prompt = ChatPromptTemplate.from_template(SAFETY_PROMPT)
    chain = prompt | structured_llm
    
    try:
        report = chain.invoke({
            "company_name": company_name,
            "draft_content": draft_content,
            "brand_persona": json.dumps(persona, ensure_ascii=False) if persona else "Tono estándar corporativo",
            "brand_guidelines_context": brand_guidelines or "No se definieron pautas específicas en el RAG."
        })
        
        if hasattr(report, "model_dump"):
            report_dict = report.model_dump()
        elif hasattr(report, "dict"):
            report_dict = report.dict()
        else:
            report_dict = dict(report)

        report_dict["evaluated"] = True

        # Normalización de consistencia: sin severidad accionable no hay
        # infracción real (alinea el veredicto con el gate del supervisor,
        # que solo recicla con severidad medium/high/critical).
        severity = (report_dict.get("severity") or "none").lower()
        report_dict["severity"] = severity
        if not report_dict.get("approved") and severity in ("none", "low"):
            logger.info(
                "Safety Guard: normalizando veredicto inconsistente "
                "(approved=false con severity=%s) -> aprobado con sugerencias.",
                severity,
            )
            report_dict["approved"] = True

        if not report_dict.get("approved"):
            logger.info(
                "❌ SAFETY GUARD detectó problemas. Severidad: %s. Fallos: %s",
                report_dict.get("severity"), report_dict.get("issues"),
            )
            return {"safety_report": report_dict, "correction_loops": loops + 1}
        else:
            logger.info("✅ SAFETY GUARD aprobado. El post cumple todas las políticas de marca.")
            return {"safety_report": report_dict}

    except Exception as e:
        logger.error(f"Fallo en la ejecución de Safety Guard: {e}")
        # Fail-open documentado: no bloquea el grafo, pero se marca como NO evaluado
        # para que la UI distinga 'aprobado' de 'no auditado'.
        return {
            "safety_report": {
                "approved": True,
                "evaluated": False,
                "issues": [],
                "severity": "none",
                "suggestions": [f"Revisión omitida por error técnico: {e}"]
            }
        }
