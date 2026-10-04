# File: tests/test_services/test_restic_service.py
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from restikls.defaults import DefaultConfig
from restikls.lib.exceptions import (
    KeyNotFoundError,
    ResticServiceError,
    ResticValidationError,
)
from restikls.models.run_options import RunOptions
from restikls.services.command_builder import CommandSpec
from restikls.services.validator_service import repository as validate_repository


def test_get_snapshots_cache_hit(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshots with cache hit."""
    with app.app_context():
        cache_key = "mock_cache_key"
        snapshots = [
            {"id": "2", "time": "2023-01-01"},
            {"id": "1", "time": "2023-01-02"},
        ]
        # snapshots.sort(key=lambda x: x['id'], reverse=False)
        cache_service.generate_key.return_value = cache_key
        cache_service.has.return_value = True
        cache_service.get.return_value = snapshots

        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshots",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "--json"], run_options=RunOptions()
            ),
        ):
            result = restic_service_local.get_snapshots(filters={"sort": "asc"})

        assert result == snapshots
        cache_service.get.assert_called_with(cache_key)
        cache_service.set.assert_not_called()


def test_get_snapshots_subprocess(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshots with subprocess execution."""
    cache_key = "mock_cache_key"
    snapshots = [
        {
            "id": "2",
            "short_id": "22222222",
            "time": "2023-01-02",
            "paths": ["/"],
            "hostname": "host1",
            "username": "user1",
            "tags": ["tag1"],
        },
        {
            "id": "1",
            "short_id": "11111111",
            "time": "2023-01-01",
            "paths": ["/"],
            "hostname": "host1",
            "username": "user1",
            "tags": ["tag1"],
        },
    ]
    sorted_snapshots = list(reversed(snapshots))

    mock_result = MagicMock(stdout=json.dumps(snapshots), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshots",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "--json"],
                run_options=RunOptions(timeout=DefaultConfig.SUBPROCESS_TIMEOUT),
            ),
        ):
            result = restic_service_local.get_snapshots(
                filters={"tags": "tag1 tag2", "hosts": "host1", "sort": "asc"}
            )

    assert result == list(reversed(snapshots))  # Ascending order
    # result snapshots would be by-value sorted after caching.
    # so returned value and cached value is the sorted one.
    cache_service.set.assert_called_with(cache_key, sorted_snapshots)
    mock_run.assert_called_once()


def test_get_snapshots_timeout(restic_service_local, local_config, cache_service, app):
    """Test get_snapshots timeout handling."""
    cache_key = "mock_cache_key"
    cache_service.generate_key.return_value = cache_key

    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["restic", "snapshots"], timeout=60),
    ) as mock_run:
        with pytest.raises(ResticServiceError, match=r".*timed out*"):
            with app.app_context():
                restic_service_local.get_snapshots()
        mock_run.assert_called_once()


def test_get_snapshot_files(restic_service_local, local_config, cache_service, app):
    """Test get_snapshot_files with subprocess execution."""
    cache_key = "mock_cache_key"
    # Snapshot header is the first line, files are subsequent lines
    snapshot_header = {"id": "abc123", "time": "2023-01-01", "paths": ["/"]}
    files = [
        {
            "path": "/file1",
            "name": "file1",
            "type": "file",
            "mtime": "2023-01-01T00:00:00Z",
            "size": 100,
        },
        {
            "path": "/file2",
            "name": "file2",
            "type": "file",
            "mtime": "2023-01-01T00:00:00Z",
            "size": 200,
        },
    ]
    all_lines = [snapshot_header] + files
    # Mock stdout should be newline-delimited JSON strings
    mock_stdout = "\n".join([json.dumps(line) for line in all_lines])

    mock_result = MagicMock(stdout=mock_stdout, stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.ls",
            return_value=CommandSpec(
                argv=["restic", "ls", "abc123", "--json"],
                run_options=RunOptions(timeout=DefaultConfig.FILE_OPERATIONS_TIMEOUT),
            ),
        ):
            header, file_list = restic_service_local.get_snapshot_files("abc123")
        mock_run.assert_called_once()

    assert header == snapshot_header
    assert file_list == files
    cache_service.set.assert_called_with(cache_key, all_lines)


def test_dump_file(restic_service_local, local_config, cache_service, app):
    """Test dump_file with subprocess execution."""
    cache_key = "mock_cache_key"
    file_content = b"test file content"
    mock_result = MagicMock(stdout=file_content, stderr=b"", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.dump",
            return_value=CommandSpec(
                argv=["restic", "dump", "--quiet", "abc123", "/file.txt"],
                run_options=RunOptions(timeout=DefaultConfig.FILE_OPERATIONS_TIMEOUT, text=False),
            ),
        ):
            result = restic_service_local.dump_file("abc123", "/file.txt")

    assert result == file_content
    cache_service.set.assert_not_called()


def test_get_file_history(restic_service_local, local_config, cache_service, app):
    """Test get_file_history with subprocess execution."""
    cache_key = "mock_cache_key"
    history = [
        {
            "snapshot": "abc123",
            "matches": [
                {
                    "path": "/file.txt",
                    "type": "file",
                    "mtime": "2023-01-01T00:00:00Z",
                    "size": 100,
                }
            ],
        }
    ]
    mock_result = MagicMock(stdout=json.dumps(history), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.find",
            return_value=CommandSpec(
                argv=["restic", "find", "--quiet", "--json", "/file.txt"],
                run_options=RunOptions(timeout=DefaultConfig.SUBPROCESS_TIMEOUT),
            ),
        ):
            result = restic_service_local.get_file_history("/file.txt", ["/path1"])

    assert result == history
    cache_service.set.assert_called_with(cache_key, history)


def test_get_keys(restic_service_local, local_config, cache_service, app):
    """Test get_keys with subprocess execution."""
    cache_key = "mock_cache_key"
    keys = [
        {"id": "key1", "userName": "user1", "hostName": "host1", "created": "2023-01-01"},
        {"id": "key2", "userName": "user2", "hostName": "host2", "created": "2023-01-02"},
    ]
    mock_result = MagicMock(stdout=json.dumps(keys), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.key_list",
            return_value=CommandSpec(
                argv=["restic", "key", "list", "--json"],
                run_options=RunOptions(timeout=DefaultConfig.SUBPROCESS_TIMEOUT),
            ),
        ):
            result = restic_service_local.get_keys()

    assert result == keys
    cache_service.set.assert_called_with(cache_key, keys)


def test_get_key_found(restic_service_local, local_config, cache_service, app):
    """Test get_key when key is found."""
    cache_key = "mock_cache_key"
    keys = [
        {"id": "key1", "userName": "user1", "hostName": "host1", "created": "2023-01-01"},
        {"id": "key2", "userName": "user2", "hostName": "host2", "created": "2023-01-02"},
    ]
    mock_result = MagicMock(stdout=json.dumps(keys), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.key_list",
            return_value=CommandSpec(
                argv=["restic", "key", "list", "--json"],
                run_options=RunOptions(timeout=DefaultConfig.SUBPROCESS_TIMEOUT),
            ),
        ):
            result = restic_service_local.get_key("key1")

    assert result == {"id": "key1", "userName": "user1", "hostName": "host1", "created": "2023-01-01"}


def test_get_key_not_found(restic_service_local, local_config, cache_service, app):
    """Test get_key when key is not found."""
    cache_key = "mock_cache_key"
    keys = [
        {"id": "key1", "userName": "user1", "hostName": "host1", "created": "2023-01-01"},
        {"id": "key2", "userName": "user2", "hostName": "host2", "created": "2023-01-02"},
    ]
    mock_result = MagicMock(stdout=json.dumps(keys), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.key_list",
            return_value=CommandSpec(
                argv=["restic", "key", "list", "--json"],
                run_options=RunOptions(timeout=DefaultConfig.SUBPROCESS_TIMEOUT),
            ),
        ):
            with pytest.raises(KeyNotFoundError, match="could not be found"):
                restic_service_local.get_key("key3")


def test_get_repo_stats(restic_service_local, local_config, cache_service, app):
    """Test get_repo_stats with subprocess execution."""
    cache_key = "mock_cache_key"
    stats = {"total_size": 1000, "total_blob_count": 50}
    mock_result = MagicMock(stdout=json.dumps(stats), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.stats",
            return_value=CommandSpec(
                argv=["restic", "stats", "--mode", "raw-data", "--json"],
                run_options=RunOptions(timeout=DefaultConfig.REPO_STATS_TIMEOUT),
            ),
        ):
            result = restic_service_local.get_repo_stats()

    assert result == stats
    cache_service.set.assert_called_with(cache_key, stats)


def test_check_repo(restic_service_local, local_config, cache_service, app):
    """Test check repository command."""
    mock_output = {"message": "no errors found"}
    mock_result = MagicMock(stdout=json.dumps(mock_output), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.check",
            return_value=CommandSpec(argv=["restic", "check", "--json"], run_options=RunOptions()),
        ):
            result = restic_service_local.check()

    assert result == mock_output
    cache_service.set.assert_not_called()


@patch("restikls.lib.utils.manage_ssh_key_file")
@patch("restikls.services.command_builder.ResticCommandBuilder")
@patch("subprocess.run")
def test_validate_repository_success(
    mock_run, mock_builder_class, mock_ssh_cm, app, restic_service_local
):
    """Test validate_repository successful case."""
    with app.app_context():
        mock_run.return_value = MagicMock(returncode=0, stderr=b"", stdout=b"[]")
        mock_builder_instance = MagicMock()
        mock_builder_instance.validate_repository.return_value = CommandSpec(argv=["cmd"], run_options=RunOptions())
        mock_builder_class.return_value = mock_builder_instance
        mock_ssh_cm.return_value.__enter__.return_value = "/tmp/key"

        is_valid, err_msg = validate_repository("/repo", "key", "ssh-key-content")

        assert is_valid is True
        assert err_msg is None


@patch("restikls.lib.utils.manage_ssh_key_file")
@patch("subprocess.run")
def test_validate_repository_auth_fail(
    mock_run, mock_ssh_cm, app, restic_service_local
):
    """Test validate_repository with an authentication failure."""
    with app.app_context():
        mock_result = mock_run.return_value
        mock_result.check_returncode.side_effect = subprocess.CalledProcessError(
            1, ["cmd"], stderr="Fatal: password incorrect"
        )
        # Simulate the result object that would be attached to the exception
        mock_result.stdout = ""
        mock_result.stderr = "Fatal: password incorrect"
        mock_ssh_cm.return_value.__enter__.return_value = None

        is_valid, err_msg = validate_repository("/repo", "key", "")

        assert is_valid is False
        assert err_msg == "Invalid repository key: Authentication failed."


@patch("restikls.lib.utils.manage_ssh_key_file")
@patch("subprocess.run")
def test_validate_repository_not_a_repo_fail(
    mock_run, mock_ssh_cm, app, restic_service_local
):
    """Test validate_repository with a 'not a repository' failure."""
    with app.app_context():
        mock_result = mock_run.return_value
        mock_result.check_returncode.side_effect = subprocess.CalledProcessError(
            1, ["cmd"], stderr="is not a repository"
        )
        mock_result.stdout = ""
        mock_result.stderr = "is not a repository"
        mock_ssh_cm.return_value.__enter__.return_value = None

        is_valid, err_msg = validate_repository("/repo", "key", "")

        assert is_valid is False
        assert err_msg == "The specified path is not a valid repository."


@patch("restikls.lib.utils.manage_ssh_key_file")
@patch("subprocess.run")
def test_validate_repository_timeout(mock_run, mock_ssh_cm, app, restic_service_local):
    """Test validate_repository with a timeout."""
    with app.app_context():
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cmd"], timeout=10)
        mock_ssh_cm.return_value.__enter__.return_value = None

        is_valid, err_msg = validate_repository("/repo", "key", "")

        assert is_valid is False
        assert err_msg and "Validation timed out" in err_msg


@patch("restikls.lib.utils.manage_ssh_key_file")
@patch("subprocess.run")
def test_validate_repository_file_not_found(
    mock_run, mock_ssh_cm, app, restic_service_local
):
    """Test validate_repository when restic executable is not found."""
    with app.app_context():
        mock_run.side_effect = FileNotFoundError("No such file or directory: 'restic'")
        mock_ssh_cm.return_value.__enter__.return_value = None

        is_valid, err_msg = validate_repository("/repo", "key", "")

        assert is_valid is False
        assert all(
            err_msg and word in err_msg
            for word in ["Executable", "restic", "not found"]
        )


def test_restic_service_factory(local_config, sftp_config, cache_service, app):
    """Test that the factory returns the correct service instance."""
    from restikls.services.factory import ResticServiceFactory
    from restikls.services.restic_service import ResticService

    local_service = ResticServiceFactory.get_service(local_config, cache_service)
    assert isinstance(local_service, ResticService)

    sftp_service = ResticServiceFactory.get_service(sftp_config, cache_service)
    assert isinstance(sftp_service, ResticService)


@patch("subprocess.run")
def test_local_service_executes_command(
    mock_run, restic_service_local, local_config, cache_service, app
):
    """Test that LocalResticService calls subprocess.run directly."""
    mock_run.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
    # service = ResticService(cache_service, local_config)
    service = restic_service_local

    # Using get_keys as a simple test case
    service.get_keys()

    mock_run.assert_called_once()
    # Check that it was called with the correct command and options
    args, kwargs = mock_run.call_args
    assert args[0][0] in [
        "restic",
    ]
    assert args[0][1] == "key"


@patch("restikls.services.command_executor.manage_ssh_key_file")
@patch("subprocess.run")
def test_sftp_service_executes_command(
    mock_run, mock_manage_ssh_key, restic_service_sftp, sftp_config, cache_service, app
):
    """Test that SftpResticService uses the manage_ssh_key_file context manager."""
    mock_run.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
    # Make the context manager work with the `with` statement in the test's scope
    mock_manage_ssh_key.return_value.__enter__.return_value = "/fake/ssh_key_path"

    # service = SftpResticService(cache_service, sftp_config)
    service = restic_service_sftp

    service.get_keys()

    # Assert that the context manager was used and the command was run
    mock_manage_ssh_key.assert_called_once_with(sftp_config)
    mock_run.assert_called_once()

    args, kwargs = mock_run.call_args
    assert args[0][0] in [
        "restic",
    ]
    assert args[0][1] == "key"


@patch("restikls.services.command_builder.ResticCommandBuilder")
@patch("subprocess.run")
def test_get_snapshots_and_sort(
    mock_run, mock_builder, restic_service_local, local_config, cache_service, app
):
    """Test get_snapshots method correctly calls dependencies and sorts the result."""
    snapshots_unsorted = [
        {
            "id": "1",
            "short_id": "11111111",
            "time": "2023-01-01T12:00:00Z",
            "paths": ["/"],
            "hostname": "host1",
            "username": "user1",
            "tags": [],
        },
        {
            "id": "2",
            "short_id": "22222222",
            "time": "2023-01-02T12:00:00Z",
            "paths": ["/"],
            "hostname": "host1",
            "username": "user1",
            "tags": [],
        },
    ]
    snapshots_sorted = list(reversed(snapshots_unsorted))

    mock_run.return_value = MagicMock(
        stdout=json.dumps(snapshots_sorted).encode(), stderr="", returncode=0
    )
    # Mock the builder to return a predictable command
    mock_builder.return_value.snapshots.return_value = CommandSpec(argv=["mock", "cmd"], run_options=RunOptions())

    # service = LocalResticService(cache_service, local_config)
    service = restic_service_local

    # Request descending sort (default)
    result = service.get_snapshots(filters={"sort": "desc"})

    assert result == snapshots_sorted
    # cache_service.set.assert_called_with(ANY, snapshots_sorted)


# @patch('restikls.services.restic_service.manage_ssh_key_file')
@patch("restikls.services.command_executor.manage_ssh_key_file")
@patch("subprocess.run")
def test_validate_repository_sftp_success(
    mock_run, mock_manage_ssh_key, app
):
    """Test standalone validate_repository function for a successful SFTP validation."""
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    mock_manage_ssh_key.return_value.__enter__.return_value = "/fake/key"

    is_valid, msg = validate_repository("sftp://a/b", "key", "ssh-key-content")
    assert is_valid is True
    assert msg is None
    mock_run.assert_called_once()
    mock_manage_ssh_key.assert_called_once()


@patch("subprocess.run")
def test_validate_repository_local_failure(mock_run, app):
    """Test standalone validate_repository for a local failure (e.g., wrong password)."""
    # Simulate a CalledProcessError with relevant stderr
    error_stderr = "password incorrect"
    mock_run.return_value = MagicMock(returncode=1, stderr=error_stderr)
    mock_result = mock_run.return_value
    mock_result.check_returncode.side_effect = subprocess.CalledProcessError(
        1, ["restic"], stderr=error_stderr
    )

    is_valid, msg = validate_repository("/local/repo", "wrong-key", "")

    assert is_valid is False
    assert msg and "Invalid repository key" in msg


def test_get_snapshot_cache_hit(restic_service_local, local_config, cache_service, app):
    """Test get_snapshot with cache hit."""
    with app.app_context():
        cache_key = "mock_cache_key"
        snapshots = [{"id": "abc123", "time": "2023-01-01"}]
        cache_service.generate_key.return_value = cache_key
        cache_service.has.return_value = True
        cache_service.get.return_value = snapshots

        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshot",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "abc123", "--json"], run_options=RunOptions()
            ),
        ):
            result = restic_service_local.get_snapshot(snapshot_id="abc123")

        assert result == snapshots
        cache_service.get.assert_called_with(cache_key)
        cache_service.set.assert_not_called()


def test_get_snapshot_subprocess_success(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshot with subprocess execution and successful retrieval."""
    cache_key = "mock_cache_key"
    snapshots = [
        {
            "id": "abc123",
            "short_id": "abc12345",
            "time": "2023-01-01",
            "paths": ["/"],
            "hostname": "host1",
            "username": "user1",
            "tags": [],
        }
    ]
    mock_result = MagicMock(stdout=json.dumps(snapshots), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshot",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "abc123", "--json"], run_options=RunOptions()
            ),
        ):
            result = restic_service_local.get_snapshot(snapshot_id="abc123")

    assert result == snapshots
    cache_service.set.assert_called_with(cache_key, snapshots)
    mock_run.assert_called_once()


def test_get_snapshot_not_found(restic_service_local, local_config, cache_service, app):
    """Test get_snapshot when snapshot is not found (returns empty list)."""
    cache_key = "mock_cache_key"
    snapshots = []  # Empty list for not found
    mock_result = MagicMock(stdout=json.dumps(snapshots), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshot",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "invalid_id", "--json"], run_options=RunOptions()
            ),
        ):
            result = restic_service_local.get_snapshot(snapshot_id="invalid_id")

    assert (
        result == []
    )  # Returns empty list, no exception raised per method implementation
    cache_service.set.assert_called_with(cache_key, snapshots)
    mock_run.assert_called_once()


def test_get_snapshot_timeout(restic_service_local, local_config, cache_service, app):
    """Test get_snapshot timeout handling."""
    cache_key = "mock_cache_key"
    cache_service.generate_key.return_value = cache_key

    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["restic", "snapshots"], timeout=60),
    ) as mock_run:
        with pytest.raises(ResticServiceError, match=r".*timed out*"):
            with app.app_context():
                restic_service_local.get_snapshot(snapshot_id="abc123")
        mock_run.assert_called_once()


def test_get_snapshot_subprocess_error(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshot with subprocess error (e.g., invalid command)."""
    cache_key = "mock_cache_key"
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["restic", "snapshots", "abc123"], stderr="error message"
        )
        with pytest.raises(ResticServiceError, match=r".*operation failed*"):
            with app.app_context():
                restic_service_local.get_snapshot(snapshot_id="abc123")
        mock_run.assert_called_once()


def test_get_snapshot_json_decode_error(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshot with invalid JSON output."""
    cache_key = "mock_cache_key"
    mock_result = MagicMock(stdout="invalid json", stderr="", returncode=0)
    mock_result.check_returncode.return_value = None

    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshot",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "abc123", "--json"], run_options=RunOptions()
            ),
        ):
            with pytest.raises(ValueError, match=r".*parse snapshots output*"):
                restic_service_local.get_snapshot(snapshot_id="abc123")

    mock_run.assert_called_once()
    cache_service.set.assert_not_called()


def test_get_snapshots_validation_missing_required_field(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshots raises ResticValidationError when required field is missing."""
    cache_key = "mock_cache_key"
    # Missing short_id
    invalid_snapshots = [
        {
            "id": "1",
            "time": "2023-01-01",
            "paths": ["/"],
            "hostname": "host1",
            "username": "user1",
            "tags": [],
        }
    ]
    mock_result = MagicMock(stdout=json.dumps(invalid_snapshots), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshots",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "--json"], run_options=RunOptions()
            ),
        ):
            with pytest.raises(ResticValidationError, match="Missing required field 'short_id'"):
                restic_service_local.get_snapshots()


def test_get_snapshots_validation_wrong_field_type(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshots raises ResticValidationError when field type is incorrect."""
    cache_key = "mock_cache_key"
    # paths is int instead of list[str]
    invalid_snapshots = [
        {
            "id": "1",
            "short_id": "11111111",
            "time": "2023-01-01",
            "paths": 12345,
            "hostname": "host1",
            "username": "user1",
            "tags": [],
        }
    ]
    mock_result = MagicMock(stdout=json.dumps(invalid_snapshots), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.snapshots",
            return_value=CommandSpec(
                argv=["restic", "snapshots", "--json"], run_options=RunOptions()
            ),
        ):
            with pytest.raises(ResticValidationError, match="must be list"):
                restic_service_local.get_snapshots()


def test_get_snapshot_files_validation_missing_file_field(
    restic_service_local, local_config, cache_service, app
):
    """Test get_snapshot_files raises when file entry is missing required fields."""
    cache_key = "mock_cache_key"
    snapshot_header = {"id": "abc123", "time": "2023-01-01", "paths": ["/"]}
    # Missing size, name, type, mtime
    invalid_files = [{"path": "/file1"}]
    all_lines = [snapshot_header] + invalid_files
    mock_stdout = "\n".join([json.dumps(line) for line in all_lines])

    mock_result = MagicMock(stdout=mock_stdout, stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.ls",
            return_value=CommandSpec(
                argv=["restic", "ls", "abc123", "--json"], run_options=RunOptions()
            ),
        ):
            # get_snapshot_files catches ResticServiceError and re-raises SnapshotNotFoundError
            from restikls.lib.exceptions import SnapshotNotFoundError

            with pytest.raises((SnapshotNotFoundError, ResticValidationError)):
                restic_service_local.get_snapshot_files("abc123")


def test_get_file_history_validation_missing_matches(
    restic_service_local, local_config, cache_service, app
):
    """Test get_file_history raises ResticValidationError when matches is missing."""
    cache_key = "mock_cache_key"
    invalid_history = [{"snapshot": "abc123"}]
    mock_result = MagicMock(stdout=json.dumps(invalid_history), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.find",
            return_value=CommandSpec(
                argv=["restic", "find", "--quiet", "--json", "/file.txt"],
                run_options=RunOptions(),
            ),
        ):
            with pytest.raises(ResticValidationError, match="Missing required field 'matches'"):
                restic_service_local.get_file_history("/file.txt", ["/path1"])


def test_get_file_history_validation_match_missing_mtime(
    restic_service_local, local_config, cache_service, app
):
    """Test get_file_history raises ResticValidationError when match is missing mtime."""
    cache_key = "mock_cache_key"
    invalid_history = [
        {
            "snapshot": "abc123",
            "matches": [{"path": "/file.txt", "type": "file", "size": 100}],
        }
    ]
    mock_result = MagicMock(stdout=json.dumps(invalid_history), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.find",
            return_value=CommandSpec(
                argv=["restic", "find", "--quiet", "--json", "/file.txt"],
                run_options=RunOptions(),
            ),
        ):
            with pytest.raises(ResticValidationError, match="Missing required field 'mtime'"):
                restic_service_local.get_file_history("/file.txt", ["/path1"])


def test_get_keys_validation_missing_field(
    restic_service_local, local_config, cache_service, app
):
    """Test get_keys raises ResticValidationError when a key is missing userName."""
    cache_key = "mock_cache_key"
    invalid_keys = [{"id": "key1", "hostName": "host1", "created": "2023-01-01"}]
    mock_result = MagicMock(stdout=json.dumps(invalid_keys), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.key_list",
            return_value=CommandSpec(
                argv=["restic", "key", "list", "--json"], run_options=RunOptions()
            ),
        ):
            with pytest.raises(ResticValidationError, match="Missing required field 'userName'"):
                restic_service_local.get_keys()


def test_get_repo_stats_validation_missing_total_size(
    restic_service_local, local_config, cache_service, app
):
    """Test get_repo_stats raises ResticValidationError when total_size is missing."""
    cache_key = "mock_cache_key"
    invalid_stats = {"total_blob_count": 50}
    mock_result = MagicMock(stdout=json.dumps(invalid_stats), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.stats",
            return_value=CommandSpec(
                argv=["restic", "stats", "--mode", "raw-data", "--json"],
                run_options=RunOptions(),
            ),
        ):
            with pytest.raises(ResticValidationError, match="Missing required field 'total_size'"):
                restic_service_local.get_repo_stats()


def test_get_repo_stats_validation_wrong_type(
    restic_service_local, local_config, cache_service, app
):
    """Test get_repo_stats raises ResticValidationError when total_size is not int."""
    cache_key = "mock_cache_key"
    invalid_stats = {"total_size": "not_an_int", "total_blob_count": 50}
    mock_result = MagicMock(stdout=json.dumps(invalid_stats), stderr="", returncode=0)
    mock_result.check_returncode.return_value = None
    cache_service.generate_key.return_value = cache_key

    with patch("subprocess.run", return_value=mock_result):
        with patch(
            "restikls.services.command_builder.ResticCommandBuilder.stats",
            return_value=CommandSpec(
                argv=["restic", "stats", "--mode", "raw-data", "--json"],
                run_options=RunOptions(),
            ),
        ):
            with pytest.raises(ResticValidationError, match="must be int"):
                restic_service_local.get_repo_stats()

