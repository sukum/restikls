# File: tests/test_models/test_restic_json.py
import pytest

from restikls.lib.exceptions import ResticValidationError
from restikls.models.restic_json import (
    DirNodePayload,
    FileNodePayload,
    NodePayload,
    parse_check,
    parse_dir_node,
    parse_file_history,
    parse_file_match,
    parse_file_node,
    parse_key,
    parse_keys,
    parse_node,
    parse_repo_stats,
    parse_snapshot,
    parse_snapshot_files,
    parse_snapshot_header,
    parse_snapshots,
)


def test_parse_snapshots_valid():
    raw = [
        {
            "id": "full_id_123",
            "short_id": "full_id_",
            "time": "2023-10-27T10:00:00.000Z",
            "paths": ["/home/user"],
            "hostname": "test-box",
            "username": "tester",
            "tags": ["daily", "prod"],
            "summary": {"files_new": 10},
        }
    ]
    result = parse_snapshots(raw)
    assert len(result) == 1
    assert result[0]["id"] == "full_id_123"
    assert result[0]["short_id"] == "full_id_"
    assert "tags" in result[0] and result[0]["tags"] == ["daily", "prod"]


def test_parse_snapshots_tags_none_normalized():
    raw = [
        {
            "id": "full_id_123",
            "short_id": "full_id_",
            "time": "2023-10-27T10:00:00.000Z",
            "paths": ["/home/user"],
            "hostname": "test-box",
            "username": "tester",
            "tags": None,
        }
    ]
    result = parse_snapshots(raw)
    assert "tags" in result[0] and result[0]["tags"] == []


def test_parse_snapshots_not_a_list():
    with pytest.raises(ResticValidationError, match="Expected snapshots output to be a JSON list"):
        parse_snapshots({"id": "not_a_list"})


def test_parse_snapshots_missing_field():
    raw = [
        {
            "id": "full_id_123",
            "time": "2023-10-27T10:00:00.000Z",
            "paths": ["/home/user"],
            "hostname": "test-box",
            "username": "tester",
            "tags": [],
        }
    ]
    with pytest.raises(ResticValidationError, match="Missing required field 'short_id'"):
        parse_snapshots(raw)


def test_parse_snapshot_empty():
    assert parse_snapshot([]) == []


def test_parse_snapshot_files_valid():
    raw = [
        {"id": "snap_1", "time": "2023-01-01", "paths": ["/data"]},
        {"path": "/data/a.txt", "name": "a.txt", "type": "file", "mtime": "2023-01-01", "size": 128},
        {"path": "/data/sub", "name": "sub", "type": "dir", "mtime": "2023-01-01", "size": 0},
        {
            "name": "src",
            "type": "dir",
            "path": "/src",
            "uid": 0,
            "gid": 0,
            "mode": 2147484159,
            "permissions": "drwxrwxrwx",
            "mtime": "2025-07-23T23:05:31.8519408+05:30",
            "atime": "2025-07-23T23:05:31.8519408+05:30",
            "ctime": "2025-07-23T23:05:31.8519408+05:30",
            "message_type": "node",
            "struct_type": "node",
        },
    ]
    header, files = parse_snapshot_files(raw)
    assert header["id"] == "snap_1"
    assert len(files) == 3
    assert files[0]["path"] == "/data/a.txt"
    assert "size" in files[0] and files[0]["size"] == 128
    assert files[1]["type"] == "dir"
    assert files[2]["type"] == "dir"
    assert files[2]["name"] == "src"
    assert "size" not in files[2]


def test_parse_snapshot_files_empty():
    with pytest.raises(ResticValidationError, match="non-empty list"):
        parse_snapshot_files([])


def test_parse_snapshot_files_missing_node_size():
    raw = [
        {"id": "snap_1", "time": "2023-01-01", "paths": ["/data"]},
        {"path": "/data/a.txt", "name": "a.txt", "type": "file", "mtime": "2023-01-01"},
    ]
    with pytest.raises(ResticValidationError, match="Missing required field 'size'"):
        parse_snapshot_files(raw)


def test_parse_dir_node_valid():
    item = {
        "name": "src",
        "type": "dir",
        "path": "/src",
        "uid": 0,
        "gid": 0,
        "mode": 2147484159,
        "permissions": "drwxrwxrwx",
        "mtime": "2025-07-23T23:05:31.8519408+05:30",
        "atime": "2025-07-23T23:05:31.8519408+05:30",
        "ctime": "2025-07-23T23:05:31.8519408+05:30",
        "message_type": "node",
        "struct_type": "node",
    }
    result = parse_dir_node(item)
    assert result["name"] == "src"
    assert result["type"] == "dir"
    assert "size" not in result


def test_parse_dir_node_missing_required_field():
    item = {"name": "src", "type": "dir"}
    with pytest.raises(ResticValidationError, match="Missing required field 'path'"):
        parse_dir_node(item)


def test_parse_file_node_valid():
    item = {
        "name": "__init__.py",
        "type": "file",
        "path": "/src/restikls/cli/__init__.py",
        "uid": 0,
        "gid": 0,
        "size": 37,
        "mode": 438,
        "permissions": "-rw-rw-rw-",
        "mtime": "2026-07-27T12:56:59.3477469+05:30",
        "atime": "2026-07-27T12:56:59.3477469+05:30",
        "ctime": "2026-07-27T12:56:59.3477469+05:30",
        "message_type": "node",
        "struct_type": "node",
    }
    result = parse_file_node(item)
    assert result["name"] == "__init__.py"
    assert result["size"] == 37


def test_parse_file_node_missing_size():
    item = {
        "name": "a.txt",
        "type": "file",
        "path": "/data/a.txt",
        "mtime": "2023-01-01",
    }
    with pytest.raises(ResticValidationError, match="Missing required field 'size'"):
        parse_file_node(item)


def test_parse_node_delegates_to_file_and_dir():
    file_item = {
        "name": "a.txt",
        "type": "file",
        "path": "/data/a.txt",
        "mtime": "2023-01-01",
        "size": 128,
    }
    dir_item = {
        "name": "src",
        "type": "dir",
        "path": "/src",
        "mtime": "2023-01-01",
    }
    file_res = parse_node(file_item)
    assert "size" in file_res and file_res["size"] == 128
    dir_res = parse_node(dir_item)
    assert "size" not in dir_res


def test_parse_node_file_missing_size():
    item = {
        "name": "a.txt",
        "type": "file",
        "path": "/data/a.txt",
        "mtime": "2023-01-01",
    }
    with pytest.raises(ResticValidationError, match="Missing required field 'size'"):
        parse_node(item)


def test_parse_file_history_valid():
    raw = [
        {
            "snapshot": "snap_1",
            "hits": 1,
            "matches": [
                {
                    "path": "/data/a.txt",
                    "type": "file",
                    "mtime": "2023-01-01T12:00:00Z",
                    "size": 512,
                }
            ],
        }
    ]
    result = parse_file_history(raw)
    assert len(result) == 1
    assert result[0]["matches"][0]["mtime"] == "2023-01-01T12:00:00Z"


def test_parse_file_history_empty_matches():
    raw = [{"snapshot": "snap_1", "matches": []}]
    with pytest.raises(ResticValidationError, match="must not be empty"):
        parse_file_history(raw)


def test_parse_file_match_bool_size_rejected():
    # In Python, isinstance(True, int) is True, so verify bool is rejected
    item = {
        "path": "/data/a.txt",
        "type": "file",
        "mtime": "2023-01-01",
        "size": True,
    }
    with pytest.raises(ResticValidationError, match="must be int, got bool"):
        parse_file_match(item)


def test_parse_keys_valid():
    raw = [
        {"id": "k1", "userName": "user1", "hostName": "host1", "created": "2023-01-01", "current": True},
        {"id": "k2", "userName": "user2", "hostName": "host2", "created": "2023-01-02"},
    ]
    keys = parse_keys(raw)
    assert len(keys) == 2
    assert keys[0]["id"] == "k1"
    assert "current" in keys[0] and keys[0]["current"] is True


def test_parse_key_missing_id():
    raw = {"userName": "user1", "hostName": "host1", "created": "2023-01-01"}
    with pytest.raises(ResticValidationError, match="Missing required field 'id'"):
        parse_key(raw)


def test_parse_repo_stats_valid():
    raw = {"total_size": 1024, "total_blob_count": 42}
    stats = parse_repo_stats(raw)
    assert stats["total_size"] == 1024
    assert stats["total_blob_count"] == 42


def test_parse_repo_stats_missing_fields():
    with pytest.raises(ResticValidationError, match="Missing required field 'total_blob_count'"):
        parse_repo_stats({"total_size": 1024})


def test_parse_check_valid():
    raw = {"message": "no errors found"}
    check = parse_check(raw)
    assert check == raw
