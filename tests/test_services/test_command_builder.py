# File: tests/test_services/test_command_builder.py
import pytest
# from dataclasses import dataclass
import time

from restikls.defaults import DefaultConfig
from restikls.lib.config import build_environment_config
from restikls.services.command_builder import CommandSpec, ResticCommandBuilder
from restikls.models.credentials import ResticCredentials
from restikls.models.run_options import RunOptions


@pytest.fixture
def mock_config():
    """Fixture for a sample config dictionary."""
    dummy_cred = ResticCredentials(
        repo_path = "/test/repo",
        repo_key  = "test_password",
        timestamp = time.time()
    )
    return dummy_cred

@pytest.fixture
def mock_run_options(mock_config, app):
    """Fixture for a sample run options dictionary."""
    run_options = RunOptions(
        timeout=1,
        env=build_environment_config(
            mock_config.repo_path, 
            mock_config.repo_key
        )
    )
    return run_options


def test_snapshots_restic(mock_config, mock_run_options, app):
    """Test snapshots command construction for restic."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.snapshots(tags=["tag1", "tag2"], hosts=["host1"])

    expected_cmd = [
        "restic",
        "snapshots",
        "--json",
        "--tag",
        "tag1",
        "--tag",
        "tag2",
        "--host",
        "host1",
    ]
    expected_timeout = DefaultConfig.SUBPROCESS_TIMEOUT

    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == expected_timeout
    assert spec.run_options.env.items() >= mock_run_options.env.items()
    assert spec.run_options.capture_output is True
    assert spec.run_options.text is True


def test_snapshots_empty_filters(mock_config, app):
    """Test snapshots command with empty tags and hosts."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.snapshots(tags=[], hosts=[])

    expected_cmd = ["restic", "snapshots", "--json"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.SUBPROCESS_TIMEOUT


def test_snapshot(mock_config, app):
    """Test snapshot command construction."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.snapshot(snapshot_id="abc123")

    expected_cmd = ["restic", "snapshots", "--json", "--", "abc123"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.SUBPROCESS_TIMEOUT
    assert spec.run_options.text is True


def test_ls(mock_config, app):
    """Test ls command construction."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.ls(snapshot_id="abc123")

    expected_cmd = ["restic", "ls", "--json", "--", "abc123"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.SUBPROCESS_TIMEOUT
    assert spec.run_options.text is True


def test_find(mock_config, app):
    """Test find command construction."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.find(
        file_path="/test/file.txt", paths=["/path1", "/path2"]
    )

    expected_cmd = [
        "restic",
        "find",
        "--quiet",
        "--json",
        "--path",
        "/path1",
        "--path",
        "/path2",
        "--",
        "/test/file.txt",
    ]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.SUBPROCESS_TIMEOUT
    assert spec.run_options.text is True


def test_file_metadata(mock_config, app):
    """Test file_metadata command construction."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.file_metadata(snapshot_id="abc123", file_path="/test/file.txt")

    expected_cmd = [
        "restic",
        "find",
        "--quiet",
        "--json",
        "--snapshot",
        "abc123",
        "--",
        "/test/file.txt",
    ]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.SUBPROCESS_TIMEOUT
    assert spec.run_options.text is False


def test_dump_restic(mock_config, app):
    """Test dump command construction for restic."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.dump(snapshot_id="abc123", file_path="/test/file.txt")

    expected_cmd = ["restic", "dump", "--quiet", "--", "abc123", "/test/file.txt"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.FILE_OPERATIONS_TIMEOUT
    assert spec.run_options.text is False


def test_stats_restic(mock_config, app):
    """Test stats command construction for restic."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.stats(mode="raw-data")

    expected_cmd = ["restic", "stats", "--mode", "raw-data", "--json"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.REPO_STATS_TIMEOUT
    assert spec.run_options.text is True


def test_key_list(mock_config, app):
    """Test key_list command construction."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.key_list()

    expected_cmd = ["restic", "key", "list", "--json"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.SUBPROCESS_TIMEOUT
    assert spec.run_options.text is True


def test_check(mock_config, app):
    """Test check command construction."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.check()

    expected_cmd = ["restic", "check", "--json"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.MAINTENANCE_CHECK_TIMEOUT
    assert spec.run_options.text is True


def test_validate_repository(mock_config, app):
    """Test validate_repository command construction."""
    builder = ResticCommandBuilder(mock_config)
    spec = builder.validate_repository()

    expected_cmd = ["restic", "snapshots", "latest", "--no-lock", "--json"]
    assert isinstance(spec, CommandSpec)
    assert spec.argv == expected_cmd
    assert spec.run_options.timeout == DefaultConfig.SUBPROCESS_TIMEOUT
    assert spec.run_options.text is True
