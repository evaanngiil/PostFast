"""
Pruebas unitarias para la autenticación y refresco de tokens OAuth de LinkedIn.
Cubre la renovación automática de tokens expirados y la actualización de fotos de perfil.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.social_apis import refresh_linkedin_access_token
from src.supabase_auth import ensure_valid_linkedin_token


def test_refresh_linkedin_access_token_success():
    """Verifica que refresh_linkedin_access_token devuelve el payload esperado cuando LinkedIn responde 200."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "access_token": "new_access_token_xyz",
        "refresh_token": "new_refresh_token_xyz",
        "expires_in": 5184000,
        "refresh_token_expires_in": 31536000,
        "scope": "openid profile email w_member_social",
        "token_type": "Bearer",
    }

    with patch("src.social_apis.LI_CLIENT_ID", "dummy_id"), \
         patch("src.social_apis.LI_CLIENT_SECRET", "dummy_secret"), \
         patch("requests.post", return_value=fake_response) as mock_post:
        result = refresh_linkedin_access_token("valid_refresh_token_123")

        assert result is not None
        assert result["access_token"] == "new_access_token_xyz"
        assert result["refresh_token"] == "new_refresh_token_xyz"
        mock_post.assert_called_once()
        _, called_kwargs = mock_post.call_args
        assert "grant_type" in called_kwargs["data"]
        assert called_kwargs["data"]["grant_type"] == "refresh_token"
        assert called_kwargs["data"]["refresh_token"] == "valid_refresh_token_123"


def test_refresh_linkedin_access_token_http_error():
    """Verifica que un error HTTP (ej: 400 Bad Request o token revocado) devuelve None sin lanzar excepción."""
    fake_response = MagicMock()
    fake_response.status_code = 400
    fake_response.text = '{"error": "invalid_grant", "error_description": "refresh token is expired"}'

    with patch("src.social_apis.LI_CLIENT_ID", "dummy_id"), \
         patch("src.social_apis.LI_CLIENT_SECRET", "dummy_secret"), \
         patch("requests.post", return_value=fake_response):
        result = refresh_linkedin_access_token("expired_refresh_token")
        assert result is None


def test_refresh_linkedin_access_token_missing_credentials():
    """Verifica que si no hay credenciales de LinkedIn configuradas devuelve None."""
    with patch("src.social_apis.LI_CLIENT_ID", None), \
         patch("src.social_apis.LI_CLIENT_SECRET", None):
        result = refresh_linkedin_access_token("any_token")
        assert result is None


def test_ensure_valid_linkedin_token_no_session():
    """Verifica que si el usuario no tiene sesión de LinkedIn en BBDD devuelve None."""
    fake_sb = MagicMock()
    fake_query = MagicMock()
    fake_query.execute.return_value = MagicMock(data=[])
    fake_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value = fake_query

    with patch("src.supabase_auth.get_supabase_admin", return_value=fake_sb):
        token = ensure_valid_linkedin_token("user-uuid-123")
        assert token is None


def test_ensure_valid_linkedin_token_active_not_expired():
    """Verifica que si el token es válido y no expira en breve, se devuelve directamente sin llamar a LinkedIn."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    session_row = {
        "session_cookie_id": "sess-1",
        "access_token": "current_valid_token",
        "refresh_token": "current_refresh_token",
        "expires_at": future_time,
    }

    fake_sb = MagicMock()
    fake_query = MagicMock()
    fake_query.execute.return_value = MagicMock(data=[session_row])
    fake_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value = fake_query

    with patch("src.supabase_auth.get_supabase_admin", return_value=fake_sb), \
         patch("src.social_apis.refresh_linkedin_access_token") as mock_refresh:
        token = ensure_valid_linkedin_token("user-uuid-123")
        assert token == "current_valid_token"
        mock_refresh.assert_not_called()


def test_ensure_valid_linkedin_token_auto_refreshes_expired():
    """Verifica que si el token ha expirado, se renueva ante LinkedIn y actualiza la sesión y user_profiles."""
    past_time = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    session_row = {
        "session_cookie_id": "sess-expired-1",
        "access_token": "old_expired_token",
        "refresh_token": "valid_refresh_token",
        "expires_at": past_time,
    }

    fake_sb = MagicMock()
    # Select query
    fake_select_query = MagicMock()
    fake_select_query.execute.return_value = MagicMock(data=[session_row])
    fake_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value = fake_select_query

    # Update query
    fake_update_query = MagicMock()
    fake_sb.table.return_value.update.return_value.eq.return_value = fake_update_query

    refreshed_data = {
        "access_token": "freshly_minted_access_token",
        "refresh_token": "freshly_minted_refresh_token",
        "expires_in": 5184000,
    }
    user_info_fresh = {
        "name": "Evan Test",
        "picture": "https://media.licdn.com/fresh_avatar.jpg",
    }

    with patch("src.supabase_auth.get_supabase_admin", return_value=fake_sb), \
         patch("src.social_apis.refresh_linkedin_access_token", return_value=refreshed_data) as mock_refresh, \
         patch("src.social_apis.get_linkedin_user_info", return_value=user_info_fresh) as mock_user_info:
        token = ensure_valid_linkedin_token("user-uuid-123")

        assert token == "freshly_minted_access_token"
        mock_refresh.assert_called_once_with("valid_refresh_token")
        mock_user_info.assert_called_once_with("freshly_minted_access_token")
        # Verificar que se actualizó user_sessions
        assert fake_sb.table.return_value.update.called
