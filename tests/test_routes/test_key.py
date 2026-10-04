# File: tests/test_routes/test_key.py
from unittest.mock import Mock

import pytest

from restikls.services.restic_service import ResticService


@pytest.fixture(autouse=True)
def mock_bootstrap_config(monkeypatch):
    # already patched in fixture
    from restikls.lib.config import get_repo_cred

    # Mock get_repo_cred from above to simulate a logged-in user
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", get_repo_cred)
    return get_repo_cred


def test_list_keys_success(client, monkeypatch):
    mock_keys = [{"id": "key1", "name": "test_key"}]
    monkeypatch.setattr(ResticService, "get_keys", Mock(return_value=mock_keys))

    response = client.get("/keys")
    assert response.status_code == 200
    assert b"key1" in response.data


def test_list_keys_error(client, monkeypatch):
    from restikls.lib.exceptions import ResticServiceError

    monkeypatch.setattr(
        ResticService, "get_keys", Mock(side_effect=ResticServiceError("Keys error"))
    )

    response = client.get("/keys")
    assert response.status_code == 500
    # print(response.data)
    assert b"Keys error" in response.data


def test_key_detail_success(client, monkeypatch):
    mock_get_key = Mock(return_value={"id": "key1", "name": "test_key"})
    monkeypatch.setattr(ResticService, "get_key", mock_get_key)

    response = client.get("/key/key1")
    assert response.status_code == 200
    assert b"key1" in response.data
    mock_get_key.assert_called_with("key1")
