# File: tests/test_routes/test_manage.py
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def mock_bootstrap_config(monkeypatch):
    # already patched in fixture
    from restikls.lib.config import get_repo_cred

    # Mock get_repo_cred from above to simulate a logged-in user
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", get_repo_cred)
    return get_repo_cred


def test_index_success(client, monkeypatch):
    response = client.get("/manage/")
    assert response.status_code == 200
    assert b"cache" in response.data


def test_read_config_success(client, monkeypatch):
    # Mock get_repo_cred and app.config
    mock_app_config = {"CACHE_TYPE": "SimpleCache"}
    monkeypatch.setattr(
        "restikls.routes.manage.current_app", Mock(config=mock_app_config)
    )

    response = client.get("/manage/config")
    assert response.status_code == 200
    assert response.json == {"0": "CACHE_TYPE"}


def test_read_config_error(client, monkeypatch):
    # Mock get_repo_cred and app.config to raise an exception
    monkeypatch.setattr("restikls.routes.manage.current_app", Mock(config=None))

    response = client.get("/manage/config")
    assert response.status_code == 200
    assert b"loading config.toml failed" in response.data


def test_cache_clear_success(client, monkeypatch):
    # Mock get_repo_cred and g.cache_service
    mock_cache_service = Mock()
    mock_cache_service.clear = Mock(return_value=True)

    monkeypatch.setattr(
        "restikls.routes.manage.g", Mock(cache_service=mock_cache_service)
    )

    response = client.post("/manage/cache/clear")
    assert response.status_code == 200
    assert response.json == {"message": "success"}
    mock_cache_service.clear.assert_called_once()


def test_cache_clear_failure(client, monkeypatch):
    # Mock get_repo_cred and g.cache_service.clear to return False
    mock_cache_service = Mock()
    mock_cache_service.clear = Mock(return_value=False)

    monkeypatch.setattr(
        "restikls.routes.manage.g", Mock(cache_service=mock_cache_service)
    )

    response = client.post("/manage/cache/clear")
    assert response.status_code == 200
    assert b"failed" in response.data


def test_cache_clear_only_clears_the_current_namespace(client, monkeypatch):
    # The raw shared cache backend must not be cleared by this route
    mock_g = Mock()
    mock_g.cache_service.clear.return_value = True

    monkeypatch.setattr("restikls.routes.manage.g", mock_g)

    response = client.post("/manage/cache/clear")
    assert response.status_code == 200
    assert response.json == {"message": "success"}
    mock_g.cache.clear.assert_not_called()
