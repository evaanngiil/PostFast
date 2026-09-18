"""
Nodo Content Editor para PostFast.

Aplica ediciones quirúrgicas sobre un post existente, separando la responsabilidad
de EDITAR (este nodo) de la de GENERAR (content_writer):

1. Ediciones dirigidas por feedback humano (HITL): el usuario revisó el borrador
   y pidió cambios concretos.
2. Modo edición rápida: el usuario trae un post ya escrito y sus instrucciones
   de mejora (campos estructurados `original_post` / `edit_instructions`).

Mantiene compatibilidad con el protocolo legado en el que el frontend embebía
el post y las instrucciones dentro de la idea con marcadores de texto.
"""
from typing import Dict, Any, Optional, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.multi_agent.state import AgentState
from src.agents.multi_agent.utils import parse_post_text
from src.core.constants import SMART_LLM, GENAI_API_KEY
from src.core.logger import logger

# Marcadores del protocolo legado (frontend antiguo). Preferir siempre los
# campos estructurados original_post / edit_instructions del estado.
LEGACY_EDIT_PREFIX = "Quiero editar y mejorar este post:"
LEGACY_INSTRUCTIONS_MARKER = "Mis instrucciones de mejora:"


EDITOR_SYSTEM_PROMPT = """Eres un redactor y editor experto de contenidos para LinkedIn.
Tu única misión es editar el post de LinkedIn del usuario aplicando estrictamente el feedback/instrucciones provistas.

**REGLAS CRÍTICAS DE EDICIÓN:**
1. **PRIORIDAD ABSOLUTA DEL FEEDBACK:** Cumplir la petición del usuario es el objetivo primario y prevalece sobre cualquier otra regla de estilo o de preservación. Si te pide eliminar enlaces, URLs o hashtags, acortar o reformatear, hazlo exactamente. Si te pide AÑADIR, INCLUIR, MENCIONAR o DESARROLLAR algo (por ejemplo, mencionar explícitamente a un socio, partner o entidad como "Hispatec" o "Agrotech", o incorporar un dato), DEBES incorporarlo de verdad al texto, aunque implique escribir frases o párrafos nuevos.
2. **PRESERVACIÓN PROPORCIONAL:** Cambia solo lo necesario para satisfacer el feedback y conserva el resto del post (tema, estructura, saltos de línea y formato). Para una petición menor (quitar un enlace) el cambio es quirúrgico; para una petición que exige contenido nuevo (mencionar/desarrollar una entidad) añade el pasaje necesario y mantén intacto lo demás. Nunca reescribas el post con contenido genérico de marca ni elimines conceptos clave que el usuario no ha pedido quitar.
3. **USO DE CONTEXTO CORPORATIVO / RAG / URL:** Cuando el feedback pida incluir, mencionar o corregir un hecho, entidad o enlace, apóyate en el "Contexto RAG de la Base de Conocimientos" y en el "Contenido de la URL de Referencia" provistos, usando EXCLUSIVAMENTE esa información verídica sin inventar cifras. Menciona las entidades solicitadas por su nombre y explica su relación con la empresa a partir de ese contexto. Si se proporciona una URL de referencia, inclúyela de forma natural como enlace del CTA al final del post.
4. **FORMATO DE SALIDA:** Devuelve ÚNICAMENTE el texto final del post editado, sin comentarios, explicaciones ni preámbulos.
"""


def parse_legacy_edit_prompt(idea_text: str) -> Optional[Tuple[str, str]]:
    """
    Extrae (post_original, instrucciones) del protocolo legado embebido en texto.

    :param idea_text: Texto de la idea que podría contener los marcadores legados.
    :returns: Tupla (original, instrucciones) o None si el texto no sigue el protocolo.
    """
    if not idea_text or LEGACY_EDIT_PREFIX not in idea_text:
        return None
    parts = idea_text.split(LEGACY_INSTRUCTIONS_MARKER)
    if len(parts) != 2:
        return None
    original = parts[0].replace(LEGACY_EDIT_PREFIX, "").strip()
    instructions = parts[1].strip()
    if not original or not instructions:
        return None
    return original, instructions


def _resolve_edit_inputs(state: AgentState) -> Tuple[str, str]:
    """
    Determina el texto base y las instrucciones de edición según el contexto.

    Prioridad:
    1. Feedback HITL sobre el último borrador del pipeline.
    2. Campos estructurados del modo edición rápida.
    3. Protocolo legado embebido en la idea (compatibilidad con frontend antiguo).
    """
    user_feedback = state.get("user_feedback")
    last_draft = state.get("last_draft_content")
    if user_feedback and last_draft:
        return last_draft, user_feedback

    original = state.get("original_post")
    instructions = state.get("edit_instructions")
    if original and instructions:
        return original, instructions

    idea = state.get("fleshed_out_idea") or state.get("user_post_idea") or ""
    if isinstance(idea, dict):
        idea = idea.get("topic", "")
    legacy = parse_legacy_edit_prompt(str(idea))
    if legacy:
        return legacy

    raise ValueError(
        "Content Editor: no hay entradas de edición válidas "
        "(ni feedback+borrador, ni original_post+edit_instructions)."
    )


def run_content_editor_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- ✂️ EJECUTANDO EDITOR DE CONTENIDO ---")

    task_id = state.get("task_id")
    if task_id:
        from src.services.realtime_service import broadcast_task_status_sync
        broadcast_task_status_sync(task_id, "RUNNING", {
            "node": "Content Editor",
            "message": "Aplicando las mejoras solicitadas sobre el post..."
        })

    base_post, instructions = _resolve_edit_inputs(state)
    logger.info("Content Editor: aplicando instrucciones ('%s…')", instructions[:80])

    company_profile = state.get("company_profile") or {}
    org_urn = company_profile.get("urn", "")
    
    rag_context = ""
    if org_urn:
        from src.services.rag_service import search_knowledge
        # Buscamos información relevante en base al feedback del usuario
        try:
            rag_docs = search_knowledge(query=instructions, org_urn=org_urn, source_type="pdf_document", threshold=0.4, limit=2)
            try:
                # Enlaces de interés (web_page): recuperamos más fragmentos y descartamos
                # los micro-chunks de "título" (puntúan alto por keyword pero no aportan
                # contenido), para que el editor disponga de sustancia real cuando el
                # feedback pide mencionar o incorporar una entidad indexada.
                rag_web = search_knowledge(query=instructions, org_urn=org_urn, source_type="web_page", threshold=0.4, limit=6)
                rag_web = [d for d in rag_web if len((d.get("content") or "").strip()) >= 80][:4]
                rag_docs += rag_web
            except Exception:
                pass
            if rag_docs:
                rag_context += "\n**Contexto RAG de la Base de Conocimientos relevante para la edición:**\n"
                rag_context += "\n".join(f"- [{d.get('source_type')}]: {d.get('content')}" for d in rag_docs)
        except Exception as e:
            logger.warning(f"Editor: error buscando RAG: {e}")

        # Buscar contenido específico de la URL de referencia si la hay
        link_url = state.get("link_url")
        if link_url:
            try:
                from src.services.supabase_client import get_supabase_admin
                sb = get_supabase_admin()
                res = sb.table("company_knowledge").select("content").eq("org_urn", org_urn).eq("source_type", "web_page").like("source_id", f"{link_url}%").execute()
                rows = res.data or []
                if rows:
                    rag_context += f"\n**Contenido de la URL de Referencia ({link_url}) disponible para la edición:**\n"
                    rag_context += "\n".join(f"- {row.get('content')}" for row in rows)
                    logger.info("Content Editor: Encontrados %d chunks para la URL de referencia: %s", len(rows), link_url)
            except Exception as e:
                logger.warning(f"Editor: error buscando URL de referencia: {e}")

    human_message = f"""
**POST ORIGINAL A EDITAR:**
---
{base_post}
---

**INSTRUCCIONES DE MEJORA DEL USUARIO:**
"{instructions}"
{rag_context}

Aplica las mejoras sobre el post original y devuelve el post editado.
"""

    llm = ChatGoogleGenerativeAI(
        model=SMART_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=0.15,
    )

    # Edición en texto libre (preserva formato del original) + parseo determinista.
    raw = llm.invoke([("system", EDITOR_SYSTEM_PROMPT), ("human", human_message)]).content
    if isinstance(raw, list):
        raw = "\n".join(p if isinstance(p, str) else p.get("text", str(p)) for p in raw)
    draft = parse_post_text(raw)

    logger.info("✅ Post editado exitosamente por Content Editor.")

    # Limpia el feedback consumido y los reportes para que el supervisor
    # re-valide el post editado (fact check + safety) en el flujo normal.
    return {
        "draft_post": draft,
        "last_draft_content": base_post,
        "user_feedback": None,
        "fact_check_report": None,
        "safety_report": None,
    }
