"""
Tests unitarios y de integración para el servidor Model Context Protocol (MCP) de PostFast.

Verifica:
1. Inicialización correcta del servidor MCP y registro de las 5 herramientas oficiales.
2. Tool de búsqueda semántica en la base de conocimiento vectorial (search_company_knowledge).
3. Tool de consulta de directrices editoriales y Skills procedimentales (list_organization_skills).
4. Tool de detección de duplicados y canibalización de publicaciones (check_post_cannibalization).
5. Tool de disparo asíncrono del pipeline multi-agente (trigger_agent_generation).
6. Tool de consulta de estado del pipeline por task_id (check_pipeline_status).
"""
import asyncio
import json
from unittest.mock import MagicMock, patch

from src.mcp_server import mcp_server


def test_mcp_server_metadata_and_tool_registration():
    """
    Verifica que el servidor MCP se instancia con el nombre correcto y registra
    las 5 herramientas requeridas para la interoperabilidad del sistema.
    """
    assert mcp_server.name == "PostFast-MCP-Server"
    
    tools = asyncio.run(mcp_server.list_tools())
    tool_names = [t.name for t in tools]
    
    expected_tools = [
        "search_company_knowledge",
        "list_organization_skills",
        "check_post_cannibalization",
        "trigger_agent_generation",
        "check_pipeline_status",
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Herramienta {exp} no encontrada en el registro MCP"


def test_mcp_search_company_knowledge_tool():
    """
    Verifica la ejecución de la herramienta MCP search_company_knowledge llamando
    al servicio RAG con filtrado por organización.
    """
    mock_results = [
        {"id": "doc1", "content": "Directiva sobre banca digital", "similarity": 0.92}
    ]
    with patch("src.services.rag_service.search_knowledge", return_value=mock_results) as mock_search:
        raw_res = asyncio.run(mcp_server.call_tool(
            "search_company_knowledge",
            {"query": "banca digital", "org_urn": "urn:li:organization:123"}
        ))
        assert not raw_res.is_error
        text_content = raw_res.content[0].text
        data = json.loads(text_content)
        
        assert data["status"] == "success"
        assert data["count"] == 1
        assert data["results"][0]["content"] == "Directiva sobre banca digital"
        mock_search.assert_called_once_with(
            query="banca digital",
            org_urn="urn:li:organization:123",
            limit=5,
            threshold=0.5,
        )


def test_mcp_list_organization_skills_tool():
    """
    Verifica que list_organization_skills recupera las directrices procedimentales
    en Markdown y formatea adecuadamente la vista previa.
    """
    mock_skills = [
        {
            "id": "sk-1",
            "name": "Guía de Estilo y Generación (Base)",
            "description": "Tono profesional",
            "markdown_content": "# Reglas\n1. Profesional pero cercano\n2. Hook inicial potente",
        }
    ]
    with patch("src.services.api_client.get_all_skills", return_value=mock_skills) as mock_get_skills:
        raw_res = asyncio.run(mcp_server.call_tool(
            "list_organization_skills",
            {"org_urn": "urn:li:organization:123"}
        ))
        assert not raw_res.is_error
        data = json.loads(raw_res.content[0].text)
        
        assert data["status"] == "success"
        assert data["skills_count"] == 1
        assert data["skills"][0]["name"] == "Guía de Estilo y Generación (Base)"
        mock_get_skills.assert_called_once_with(org_urn="urn:li:organization:123")


def test_mcp_check_post_cannibalization_tool():
    """
    Verifica que check_post_cannibalization detecta publicaciones previas similares.
    """
    mock_posts = [
        {"post_id": "post-99", "content": "Post anterior sobre IA", "similarity": 0.85}
    ]
    with patch("src.services.rag_service.search_similar_posts", return_value=mock_posts) as mock_search_posts:
        raw_res = asyncio.run(mcp_server.call_tool(
            "check_post_cannibalization",
            {"query": "avances en IA generativa", "org_urn": "urn:li:organization:123"}
        ))
        assert not raw_res.is_error
        data = json.loads(raw_res.content[0].text)
        
        assert data["status"] == "success"
        assert data["similar_posts_found"] == 1
        assert data["posts"][0]["post_id"] == "post-99"
        mock_search_posts.assert_called_once()


def test_mcp_trigger_agent_generation_tool():
    """
    Verifica que trigger_agent_generation encola asíncronamente la tarea de Celery
    y retorna el task_id de forma inmediata para prevenir timeouts.
    """
    mock_task = MagicMock()
    mock_task.id = "task-uuid-test-999"

    with patch("src.tasks.content_generation_task.delay", return_value=mock_task) as mock_delay:
        raw_res = asyncio.run(mcp_server.call_tool(
            "trigger_agent_generation",
            {
                "idea": "Tendencias de computación cuántica",
                "org_urn": "urn:li:organization:123",
            }
        ))
        assert not raw_res.is_error
        data = json.loads(raw_res.content[0].text)
        
        assert data["status"] == "queued"
        assert data["task_id"] == "task-uuid-test-999"
        mock_delay.assert_called_once_with(
            payload_dict={
                "user_post_idea": "Tendencias de computación cuántica",
                "linkedin_access_token": "",
                "selected_account": {"urn": "urn:li:organization:123"},
            }
        )


def test_mcp_check_pipeline_status_tool():
    """
    Verifica que check_pipeline_status devuelve el estado actualizado de la tarea.
    """
    mock_async_result = MagicMock()
    mock_async_result.state = "RUNNING"
    mock_async_result.ready.return_value = False
    mock_async_result.info = {"current_node": "content_writer"}

    with patch("src.celery_app.celery_app.AsyncResult", return_value=mock_async_result):
        raw_res = asyncio.run(mcp_server.call_tool(
            "check_pipeline_status",
            {"task_id": "task-uuid-test-999"}
        ))
        assert not raw_res.is_error
        data = json.loads(raw_res.content[0].text)
        
        assert data["task_id"] == "task-uuid-test-999"
        assert data["state"] == "RUNNING"
        assert data["ready"] is False
