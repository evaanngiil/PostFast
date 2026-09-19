from unittest.mock import patch, MagicMock
from src.services.rag_service import search_knowledge


def test_search_knowledge_hybrid_keyword_fallback():
    mock_supabase = MagicMock()
    mock_rpc = MagicMock()
    mock_rpc.execute.return_value = MagicMock(data=[])
    mock_supabase.rpc.return_value = mock_rpc

    mock_table = MagicMock()
    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.ilike.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = MagicMock(data=[
        {"id": "doc-1", "content": "Proyecto Agrotech con Hispatec", "source_type": "pdf_document", "metadata": {}}
    ])
    mock_supabase.table.return_value = mock_query

    with patch("src.services.rag_service.generate_query_embedding", return_value=[0.1] * 768):
        with patch("src.services.rag_service.get_supabase_admin", return_value=mock_supabase):
            results = search_knowledge(query="convenio con Hispatec", org_urn="urn:li:organization:123", limit=3)
            assert len(results) == 1
            assert results[0]["id"] == "doc-1"
            assert "Hispatec" in results[0]["content"]
            mock_query.ilike.assert_called_once()
