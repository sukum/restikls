# File: tests/test_routes/test_file.py
from unittest.mock import Mock

import pytest

from restikls.lib.exceptions import FileAccessError

# from restikls.services.restic_service import ResticService
# from flask import g


@pytest.fixture(autouse=True)
def mock_bootstrap_config(monkeypatch):
    # already patched in fixture
    from restikls.lib.config import get_repo_cred

    # Mock get_repo_cred from above to simulate a logged-in user
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", get_repo_cred)
    return get_repo_cred


@pytest.fixture
def file_1():
    return {
        "path": "/test/file1.txt",
        "mtime": "2023-10-27T10:00:00.123456789Z",
        "mode": int(int("755", 8)),
    }


def test_snapshot_files_success(
    client, mock_restic_service, file_1, mock_bootstrap_config
):
    mock_snapshot_header = {"id": "snap1", "paths": ["/"]}
    mock_files = [file_1]
    mock_restic_service.get_snapshot_files.return_value = (
        mock_snapshot_header,
        mock_files,
    )

    response = client.get("/files/snapshot/snap1?page=1")
    assert response.status_code == 200
    assert b"file1.txt" in response.data
    mock_restic_service.get_snapshot_files.assert_called_with("snap1")


def test_snapshot_files_ajax(client, mock_restic_service, file_1):
    mock_snapshot_header = {"id": "snap1", "paths": ["/"]}
    mock_files = [file_1]
    mock_restic_service.get_snapshot_files.return_value = (
        mock_snapshot_header,
        mock_files,
    )

    # g.is_ajax = True
    response = client.get("/files/snapshot/snap1?page=1&is_ajax=1")
    assert response.status_code == 200
    assert b"<!DOCTYPE html>" not in response.data
    assert b"<table" in response.data
    mock_restic_service.get_snapshot_files.assert_called_with("snap1")


def test_file_history_success(client, mock_restic_service, file_1):
    mock_files = [{"matches": [file_1]}]
    # monkeypatch.setattr(g.restic_service, "get_file_history", Mock(return_value=mock_files))
    mock_restic_service.get_file_history.return_value = mock_files

    response = client.get(
        "/file/history?file_path=/file1.txt&page=1&paths=/foo&paths=/bar"
    )
    assert response.status_code == 200
    assert b"/test/file1.txt" in response.data
    mock_restic_service.get_file_history.assert_called_with(
        "/file1.txt", ["/foo", "/bar"]
    )


def test_file_download_success(client, mock_restic_service):
    mock_file_bytes = b"file content"
    mock_restic_service.dump_file = Mock(return_value=mock_file_bytes)

    response = client.post(
        "/file/download", json={"file_path": "/file1.txt", "snapshot_id": "snap1"}
    )
    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == "attachment; filename=file1.txt"
    mock_restic_service.dump_file.assert_called_with("snap1", "/file1.txt")


def test_file_view_success(client, mock_restic_service):
    mock_file_bytes = b"file content"
    mock_restic_service.dump_file = Mock(return_value=mock_file_bytes)

    response = client.get("/file/view?file_path=/file1.txt&snapshot_id=snap1")
    assert response.status_code == 200
    assert response.json["file_data"] == "file content"


def test_file_view_binary_error(client, mock_restic_service):
    """Test that file view handles non-UTF8 files gracefully."""
    binary_content = b"\x80\x81\x82"  # Invalid UTF-8 sequence
    mock_restic_service.dump_file = Mock(return_value=binary_content)

    response = client.get("/file/view?file_path=/binary.dat&snapshot_id=snap1")
    print(response.headers)
    # print(response.data.decode('utf-8'))
    assert response.status_code == 400
    assert "error_message" in response.json
    assert "binary" in response.json["error_message"]


def test_file_download_absent_file_error(client, mock_restic_service):
    """Test that file_download handles an absent file gracefully when file_metadata raises FileAccessError."""
    mock_restic_service.file_metadata.side_effect = FileAccessError(
        "Failed finding metadata for file: /absent.txt in snapshot: #snap1"
    )

    response = client.post(
        "/file/download", json={"file_path": "/absent.txt", "snapshot_id": "snap1"}
    )
    assert response.status_code == 500
    assert response.is_json
    assert "error_message" in response.json
    assert (
        "Failed finding metadata for file: /absent.txt in snapshot: #snap1"
        in response.json["error_message"]
    )
    mock_restic_service.file_metadata.assert_called_with("snap1", "/absent.txt")


def test_file_view_absent_file_error(client, mock_restic_service):
    """Test that file_view handles an absent file gracefully when file_metadata raises FileAccessError."""
    mock_restic_service.file_metadata.side_effect = FileAccessError(
        "Failed finding metadata for file: /absent.txt in snapshot: #snap1"
    )

    response = client.get("/file/view?file_path=/absent.txt&snapshot_id=snap1")
    assert response.status_code == 500
    assert response.is_json
    assert "error_message" in response.json
    assert (
        "Failed finding metadata for file: /absent.txt in snapshot: #snap1"
        in response.json["error_message"]
    )
    mock_restic_service.file_metadata.assert_called_with("snap1", "/absent.txt")

