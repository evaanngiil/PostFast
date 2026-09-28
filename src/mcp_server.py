"""
Servidor Model Context Protocol (MCP) para PostFast.

Expone las capacidades cognitivas, de memoria vectorial y de auditoría de PostFast
como herramientas (tools) estandarizadas bajo el protocolo abierto MCP (Model Context Protocol).

Permite que clientes compatibles (Claude Desktop, Cursor IDE, Zed, agentes externos)
interactúen de forma nativa e interoperable con:
1. Base de conocimiento empresarial (RAG en pgvector).
2. Catálogo de Skills procedimentales y directrices de marca en Markdown.
3. Detección de duplicados y canibalización de contenido previo en LinkedIn.
4. Disparo asíncrono y consulta de estado del pipeline multi-agente.
"""
import json

from mcp.server.mcpserver import MCPServer
from src.core.logger import logger


mcp_server = MCPServer(
    name="PostFast-MCP-Server",
    version="1.0.0",
    description="Servidor MCP oficial de PostFast para orquestación y generación asistida de contenido B2B en LinkedIn."
)


@mcp_server.tool()
def search_company_knowledge(
    query: str,
    org_urn: str,
    limit: int = 5,
    threshold: float = 0.5,
) -> str:
    """
    Busca fragmentos verídicos en la base de conocimientos vectorial (pgvector) de la organización.
    
    :param query: Texto o concepto a consultar en la documentación corporativa.
    :param org_urn: Identificador URN de la empresa (aislamiento multi-tenant).
    :param limit: Número máximo de fragmentos a recuperar (por defecto 5).
    :param threshold: Umbral mínimo de similitud coseno (0.0 a 1.0).
    :return: Lista serializada en JSON de fragmentos recuperados con su score y metadatos.
    """
    try:
        from src.services.rag_service import search_knowledge
        results = search_knowledge(
            query=query,
            org_urn=org_urn,
            limit=limit,
            threshold=threshold,
        )
        return json.dumps({
            "status": "success",
            "count": len(results),
            "results": results,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[MCP] Error en search_company_knowledge: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp_server.tool()
def list_organization_skills(org_urn: str) -> str:
    """
    Recupera el catálogo de Skills procedimentales y guías de estilo editorial en Markdown.
    
    :param org_urn: Identificador URN de la organización.
    :return: Lista de directrices de estilo disponibles para guiar la redacción.
    """
    try:
        from src.services.api_client import get_all_skills
        skills = get_all_skills(org_urn=org_urn)
        formatted = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "description": s.get("description"),
                "content_preview": (s.get("markdown_content") or "")[:200] + "...",
            }
            for s in skills
        ]
        return json.dumps({
            "status": "success",
            "skills_count": len(formatted),
            "skills": formatted,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[MCP] Error en list_organization_skills: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp_server.tool()
def check_post_cannibalization(
    query: str,
    org_urn: str,
    threshold: float = 0.70,
) -> str:
    """
    Analiza publicaciones históricas de LinkedIn de la empresa para evitar canibalización semántica o duplicados.
    
    :param query: Idea central o borrador del post a verificar.
    :param org_urn: Identificador URN de la organización.
    :param threshold: Umbral de similitud coseno para considerar posible duplicado.
    :return: Listado de publicaciones históricas semánticamente próximas.
    """
    try:
        from src.services.rag_service import search_similar_posts
        similar_posts = search_similar_posts(
            query=query,
            org_urn=org_urn,
            threshold=threshold,
        )
        return json.dumps({
            "status": "success",
            "similar_posts_found": len(similar_posts),
            "posts": similar_posts,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[MCP] Error en check_post_cannibalization: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp_server.tool()
def trigger_agent_generation(
    idea: str,
    org_urn: str,
    linkedin_access_token: str = "",
) -> str:
    """
    Dispara de forma asíncrona el flujo completo de 11 agentes de PostFast en background.
    
    Devuelve de inmediato el task_id de Celery para evitar bloqueos por timeout en el cliente MCP.
    
    :param idea: Concepto, temática o instrucción base para la publicación.
    :param org_urn: URN corporativo de la organización.
    :param linkedin_access_token: Token de acceso opcional para publicación directa.
    :return: Diccionario con task_id y estado inicial de encolamiento.
    """
    try:
        from src.tasks import content_generation_task
        payload_dict = {
            "user_post_idea": idea,
            "linkedin_access_token": linkedin_access_token,
            "selected_account": {"urn": org_urn},
        }
        task = content_generation_task.delay(payload_dict=payload_dict)
        return json.dumps({
            "status": "queued",
            "task_id": task.id,
            "message": "Generación asíncrona iniciada. Consulta el estado periódicamente con check_pipeline_status.",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[MCP] Error en trigger_agent_generation: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


@mcp_server.tool()
def check_pipeline_status(task_id: str) -> str:
    """
    Consulta el estado de ejecución de una tarea del motor multi-agente mediante su task_id.
    
    :param task_id: Identificador único de la tarea devuelto por trigger_agent_generation.
    :return: Estado actual (PENDING, RUNNING, SUCCESS, FAILURE, o awaiting_review).
    """
    try:
        from src.celery_app import celery_app
        res = celery_app.AsyncResult(task_id)
        return json.dumps({
            "task_id": task_id,
            "state": res.state,
            "ready": res.ready(),
            "info": str(res.info) if res.info else None,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[MCP] Error en check_pipeline_status: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    # Ejecución por defecto mediante transporte estándar stdio (para Claude Desktop / Cursor)
    mcp_server.run(transport="stdio")
