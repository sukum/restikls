# File: tests/test_services/test_validator_service.py

import subprocess
from unittest.mock import Mock

import pytest

from restikls.models.run_options import RunOptions
from restikls.services.command_builder import CommandSpec
from restikls.services.factory import ResticServiceFactory
from restikls.services.validator_service import repository


@pytest.fixture
def mock_setup(monkeypatch):
    """
    Fixture to mock common dependencies for validator tests.
    """

    # mock_build_env = Mock(
    #     return_value={"RESTIC_PASSWORD": "test"}, name="build_environment_config"
    # )
    # monkeypatch.setattr(
    #     "restikls.services.validator_service.build_environment_config",
    #     mock_build_env,
    # )

    mock_factory = Mock(spec=ResticServiceFactory, name="ResticServiceFactory")
    mock_service = Mock(name="get_service")
    mock_executor = Mock(name="executor")
    mock_result = Mock(name="result")
    mock_execute = Mock(name="execute", return_value=mock_result)
    mock_executor.execute = mock_execute
    mock_service.executor = mock_executor
    mock_factory.get_service.return_value = mock_service
    monkeypatch.setattr(
        "restikls.services.validator_service.ResticServiceFactory", mock_factory
    )

    mock_builder = Mock(name="ResticCommandBuilder")
    mock_builder.return_value.validate_repository = Mock(
        name="validate_repository",
        return_value=CommandSpec(
            argv=["restic", "check"], run_options=RunOptions(timeout=60)
        ),
    )
    monkeypatch.setattr(
        "restikls.services.validator_service.ResticCommandBuilder", mock_builder
    )

    # Cache is internal, no need to mock unless affecting behavior

    return mock_result


def test_repository_success(app, caplog, mock_setup):
    """
    Test successful repository validation.
    """
    mock_result = mock_setup
    mock_result.__dict__.update(args=[], returncode=0, stdout="OK", stderr="")
    # mock_executor.execute.return_value = mock_result

    success, error = repository("sftp://test", "key", "ssh_key")

    assert success is True
    assert error is None
    assert "Successfully validated repository" in caplog.text


def test_repository_timeout(app, caplog, mock_setup):
    """
    Test validation timeout.
    """
    mock_result = mock_setup
    mock_result.check_returncode.side_effect = subprocess.TimeoutExpired(
        cmd=[], timeout=60
    )

    success, error = repository("/test/repo", "key", "")

    assert success is False
    assert error and "timed out" in error
    assert "timed out" in caplog.text


def test_repository_called_process_error_invalid_key(app, caplog, mock_setup):
    """
    Test CalledProcessError with invalid key message.
    """
    mock_result = mock_setup
    mock_result.__dict__.update(
        args=[], returncode=1, stdout="", stderr="password incorrect"
    )
    mock_result.check_returncode.side_effect = subprocess.CalledProcessError(
        1, cmd=[], stderr="password incorrect"
    )

    success, error = repository("/test/repo", "wrong_key", "")

    assert success is False
    assert error and "failed" in error
    assert "password incorrect" in caplog.text


def test_repository_called_process_error_not_repo(app, caplog, mock_setup):
    """
    Test CalledProcessError when not a repository.
    """
    mock_result = mock_setup
    mock_result.__dict__.update(
        args=[], returncode=1, stdout="", stderr="is not a repository"
    )
    mock_result.check_returncode.side_effect = subprocess.CalledProcessError(
        1, cmd=[], stderr="is not a repository"
    )

    success, error = repository("/invalid", "key", "")

    assert success is False
    assert error and "not a valid repository" in error
    assert "is not a repository" in caplog.text


def test_repository_called_process_error_generic(app, caplog, mock_setup):
    """
    Test generic CalledProcessError.
    """
    mock_result = mock_setup
    mock_result.__dict__.update(
        args=[], returncode=1, stdout="", stderr="permission denied"
    )
    mock_result.check_returncode.side_effect = subprocess.CalledProcessError(
        1, cmd=[], stderr="permission denied"
    )

    success, error = repository("/test/repo", "key", "")

    assert success is False
    assert error and "permission denied" in error
    assert "permission denied" in caplog.text


def test_repository_file_not_found(app, caplog, mock_setup):
    """
    Test FileNotFoundError when restic not found.
    """
    mock_result = mock_setup
    mock_result.check_returncode.side_effect = FileNotFoundError("restic not found")

    success, error = repository("/test/repo", "key", "")

    assert success is False
    assert error and "not found" in error
    assert all(_text in caplog.text for _text in ["restic", "not found"])


def test_repository_unexpected_exception(app, caplog, mock_setup):
    """
    Test unexpected exception during validation.
    """
    mock_result = mock_setup
    mock_result.check_returncode.side_effect = ValueError("Unexpected error")

    success, error = repository("/test/repo", "key", "")

    assert success is False
    assert error and "Unexpected error" in error
    assert "Unexpected error" in caplog.text


def test_repository_with_stderr_warning(app, caplog, mock_setup):
    """
    Test successful validation but with stderr warning.
    """
    mock_result = mock_setup
    mock_result.__dict__.update(
        args=[], returncode=0, stdout="OK", stderr="minor warning"
    )

    success, error = repository("/test/repo", "key", "")

    assert success is True
    assert error is None
    assert "minor warning" in caplog.text
