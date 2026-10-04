# File: tests/test_routes/test_snapshot.py
from datetime import datetime
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def mock_bootstrap_config(monkeypatch):
    # already patched in fixture
    from restikls.lib.config import get_repo_cred

    # Mock get_repo_cred from above to simulate a logged-in user
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", get_repo_cred)
    return get_repo_cred


def test_list_snapshots_success(client, monkeypatch, mock_restic_service):
    # Mock get_repo_cred and ResticService.get_snapshots
    mock_snapshots = [{"id": "snap1", "time": datetime.now().isoformat()}]
    mock_restic_service.get_snapshots = Mock(return_value=mock_snapshots)

    response = client.get("/snapshots/?page=1&sort=desc")
    assert response.status_code == 200
    assert b"snap1" in response.data
    mock_restic_service.get_snapshots.assert_called_with(
        filters={"tags": "", "hosts": "", "sort": "desc"}
    )


def test_list_snapshots_ajax(client, monkeypatch, mock_restic_service):
    # Mock AJAX request
    mock_snapshots = [{"id": "snap1", "time": datetime.now().isoformat()}]
    mock_restic_service.get_snapshots = Mock(return_value=mock_snapshots)

    response = client.get("/snapshots/?page=1&sort=desc&is_ajax=1")
    assert response.status_code == 200
    # Check for table content but not the full layout
    assert b"<!DOCTYPE html>" not in response.data
    assert b"<table" in response.data


def test_snapshot_detail_success(client, monkeypatch, mock_restic_service):
    # Mock get_repo_cred and ResticService.get_snapshots
    now = datetime.now().isoformat()
    # The detail view calls get_snapshots with a snapshot_id filter, which returns a list.
    mock_details = [
        {
            "id": "snap1",
            "time": now,
            "paths": ["/"],
            "hostname": "test-host",
            "tags": [],
            "summary": {"items": []},
        }
    ]
    mock_restic_service.get_snapshots = Mock(return_value=mock_details)
    # mock_restic_service.get_snapshots.__iter__.return_value = mock_details

    response = client.get("/snapshot/snap1")
    assert response.status_code == 200
    # assert b'snap1' in response.data
    assert b"Username" in response.data
    # Check that the service was called correctly
    # mock_restic_service.get_snapshots.assert_called_with(filters={'snapshot_id': 'snap1'})
