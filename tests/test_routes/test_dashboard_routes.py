# File: tests/test_routes/test_dashboard_routes.py
# import pytest
from unittest.mock import MagicMock


def test_dashboard_redirects_if_no_config(client, monkeypatch):
    """Test that accessing the dashboard without config redirects to the config page."""
    monkeypatch.setattr("restikls.lib.config.get_repo_cred", MagicMock(return_value={}))
    monkeypatch.setattr(
        "restikls.routes.config_routes.get_repo_cred", MagicMock(return_value={})
    )
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/config" in response.headers["Location"]


def test_dashboard_success(app, client, monkeypatch, mock_restic_service):
    """Test that the dashboard loads successfully with a valid config."""
    # already patched in fixture
    from restikls.lib.config import get_repo_cred

    # Mock get_repo_cred from above to simulate a logged-in user
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", get_repo_cred)
    # Mock the service call that fetches stats
    mock_stats = {
        "total_size": 12345,
        "snapshots_count": 5,
        "items": MagicMock(return_value=[]),
    }
    mock_restic_service.get_repo_stats.return_value = mock_stats

    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Information" in response.data
    assert b"Statistics" in response.data
    assert b"Calculate repo statistics" in response.data
    mock_restic_service.get_repo_stats.assert_not_called()


def test_dashboard_api_stats_success(client, monkeypatch, mock_restic_service):
    """Test the API stats endpoint."""

    # already patched in fixture
    from restikls.lib.config import get_repo_cred

    # Mock get_repo_cred from above to simulate a logged-in user
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", get_repo_cred)
    mock_stats = {"total_size": 12345, "snapshots_count": 5}
    mock_restic_service.get_repo_stats.return_value = mock_stats

    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.json == mock_stats


def test_dashboard_health_success(client, monkeypatch):
    """Test the health endpoint."""

    # already patched in fixture
    from restikls.lib.config import get_repo_cred

    # Mock get_repo_cred from above to simulate a logged-in user
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", get_repo_cred)
    mock_return = {"status": "healthy"}

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == mock_return


def test_dashboard_sanitizes_rest_repo_path(app, client, monkeypatch):
    """Test that the dashboard displays sanitized repo_path for REST repos with auth."""
    import time
    from restikls.models.credentials import ResticCredentials

    rest_cred = ResticCredentials(
        repo_path="rest:http://user:secret@host:8080/repo",
        repo_key="test_key",
        timestamp=time.time(),
    )
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", lambda: rest_cred)

    response = client.get("/")
    assert response.status_code == 200
    assert b"rest:http://host:8080/repo" in response.data
    assert b"secret" not in response.data
    assert b"user:secret@" not in response.data
