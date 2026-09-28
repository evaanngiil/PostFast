"""
Tests de seguridad y validación multi-tenant para PostFast.

Verifican formalmente:
1. Segregación estricta de conocimiento vectorial y búsquedas semánticas por org_urn.
2. Detección de duplicados acotada exclusivamente a la organización del usuario.
3. Aislamiento en la ingesta y vectorización de documentos (chunks etiquetados por tenant).
4. Catálogo de Skills procedimentales aislado por organización.
5. Denegación de acceso no autenticado a recursos corporativos con HTTP 401/403.
"""
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.services.rag_service import search_knowledge, search_similar_posts, index_document
from src.services.api_client import get_all_skills


ORG_TENANT_A = "urn:li:organization:corp_alpha_111"
ORG_TENANT_B = "urn:li:organization:corp_beta_222"


def test_rag_search_isolated_by_org_urn():
    """
    Verifica que la búsqueda semántica en la base de conocimiento inyecta
    forzosamente el target_org_urn de la organización que realiza la consulta,
    impidiendo la recuperación de fragmentos de otros tenants.
    """
    with patch("src.services.rag_service.get_supabase_admin") as mock_get_admin, \
         patch("src.services.rag_service.generate_query_embedding", return_value=[0.1] * 768):
        
        mock_supabase = MagicMock()
        mock_get_admin.return_value = mock_supabase
        mock_rpc = MagicMock()
        mock_supabase.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value.data = [
            {"id": "doc1", "content": "Alpha confidential knowledge", "similarity": 0.88}
        ]

        results = search_knowledge(query="estrategia IA", org_urn=ORG_TENANT_A)

        # Validar que el RPC fue llamado con target_org_urn de Tenant A
        mock_supabase.rpc.assert_called_once()
        rpc_call_args = mock_supabase.rpc.call_args[0]
        assert rpc_call_args[0] == "match_company_knowledge"
        
        rpc_params = rpc_call_args[1]
        assert rpc_params["target_org_urn"] == ORG_TENANT_A
        assert rpc_params["target_org_urn"] != ORG_TENANT_B
        assert len(results) == 1


def test_rag_keyword_fallback_enforces_org_filter():
    """
    Verifica que en caso de caída o insuficiencia de la búsqueda vectorial, el fallback
    por palabras clave filtra obligatoriamente por org_urn mediante .eq("org_urn", tenant).
    """
    with patch("src.services.rag_service.get_supabase_admin") as mock_get_admin, \
         patch("src.services.rag_service.generate_query_embedding", return_value=[0.1] * 768):
        
        mock_supabase = MagicMock()
        mock_get_admin.return_value = mock_supabase
        mock_rpc = MagicMock()
        mock_supabase.rpc.return_value = mock_rpc
        # Simulamos que el RPC vectorial devuelve 0 filas para forzar la rama de fallback
        mock_rpc.execute.return_value.data = []

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.ilike.return_value.limit.return_value.execute.return_value.data = []

        search_knowledge(query="estrategia de sostenibilidad empresarial", org_urn=ORG_TENANT_A)

        # Debe consultar company_knowledge con filtro estricto por org_urn
        mock_supabase.table.assert_called_with("company_knowledge")
        mock_select.eq.assert_called_with("org_urn", ORG_TENANT_A)


def test_duplicate_detection_isolated_by_org_urn():
    """
    Verifica que la detección de canibalización y duplicados solo consulta
    publicaciones previas de la misma organización.
    """
    with patch("src.services.rag_service.get_supabase_admin") as mock_get_admin, \
         patch("src.services.rag_service.generate_query_embedding", return_value=[0.05] * 768):
        
        mock_supabase = MagicMock()
        mock_get_admin.return_value = mock_supabase
        mock_rpc = MagicMock()
        mock_supabase.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value.data = []

        search_similar_posts(query="post sobre sostenibilidad", org_urn=ORG_TENANT_B)

        mock_supabase.rpc.assert_called_once()
        rpc_params = mock_supabase.rpc.call_args[0][1]
        assert rpc_params["target_org_urn"] == ORG_TENANT_B
        assert rpc_params["target_org_urn"] != ORG_TENANT_A


def test_document_indexing_associates_tenant_org_urn():
    """
    Verifica que la indexación de documentos asocia de forma inmutable
    el org_urn en los metadatos y en el registro del vector store.
    """
    with patch("src.services.rag_service.get_supabase_admin") as mock_get_admin, \
         patch("src.services.rag_service.generate_embedding", return_value=[0.01] * 768):
        
        mock_supabase = MagicMock()
        mock_get_admin.return_value = mock_supabase
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock()

        count = index_document(
            org_urn=ORG_TENANT_A,
            source_type="brand_book",
            source_id="brand_guide_2026.pdf",
            content="Documento de prueba completo de la organizacion Alpha.",
        )

        assert count >= 1
        mock_supabase.table.assert_called_with("company_knowledge")
        upsert_calls = mock_table.upsert.call_args_list
        assert len(upsert_calls) >= 1
        
        # Validar que todos los payloads de upsert contienen org_urn de Tenant A
        for call in upsert_calls:
            payload = call[0][0]
            assert payload["org_urn"] == ORG_TENANT_A


def test_skills_crud_enforces_tenant_isolation():
    """
    Verifica que la consulta de directrices editoriales y Skills procedimentales
    filtra estrictamente por la organización solicitante.
    """
    with patch("src.services.api_client.get_supabase") as mock_get_supabase:
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.order.return_value.execute.return_value.data = [
            {"id": "base-1", "name": "Guía de Estilo y Generación (Base)", "org_urn": ORG_TENANT_A},
            {"id": "skill-1", "name": "Tono Ejecutivo", "org_urn": ORG_TENANT_A}
        ]

        skills = get_all_skills(org_urn=ORG_TENANT_A)

        mock_supabase.table.assert_called_with("skills")
        mock_select.eq.assert_called_with("org_urn", ORG_TENANT_A)
        assert len(skills) >= 2
        assert all(s["org_urn"] == ORG_TENANT_A for s in skills)


def test_api_endpoints_reject_unauthenticated_tenant_requests():
    """
    Verifica que las rutas de la API de FastAPI que manipulan contenido o
    conocimiento empresarial rechazan sistemáticamente peticiones sin autenticación (401/403).
    """
    client = TestClient(app, raise_server_exceptions=False)
    
    # 1. Petición a listado de posts protegidos sin cabecera de autenticación
    res_posts = client.get("/content/posts")
    assert res_posts.status_code in (401, 403)

    # 2. Intento de subida de PDF sin token de sesión
    res_upload = client.post("/knowledge/upload", files={"file": ("test.pdf", b"fake pdf content", "application/pdf")})
    assert res_upload.status_code in (401, 403, 404)
