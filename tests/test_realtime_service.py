from unittest.mock import patch, MagicMock
from src.services.realtime_service import broadcast_task_status_sync, broadcast_task_status, _get_sync_client, _get_async_client
import pytest


def test_get_sync_client_reuses_instance():
    c1 = _get_sync_client()
    c2 = _get_sync_client()
    assert c1 is c2
    assert not c1.is_closed


@pytest.mark.anyio
async def test_get_async_client_reuses_instance():
    c1 = _get_async_client()
    c2 = _get_async_client()
    assert c1 is c2
    assert not c1.is_closed


def test_broadcast_task_status_sync_uses_pooled_client():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client.post.return_value = mock_resp

    with patch("src.services.realtime_service._get_sync_client", return_value=mock_client):
        with patch("src.services.realtime_service.SUPABASE_URL", "https://example.supabase.co"):
            with patch("src.services.realtime_service.SUPABASE_KEY", "secret-key"):
                broadcast_task_status_sync("task-123", "RUNNING", {"node": "Test"})
                mock_client.post.assert_called_once()
