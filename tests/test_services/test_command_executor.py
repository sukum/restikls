# File: tests/test_services/test_command_executor.py

from dataclasses import asdict
import subprocess
import sys
from unittest.mock import patch, MagicMock
import pytest

from restikls.models.credentials import ResticCredentials
from restikls.services.command_executor import (
    LocalExecutor,
    RestServerExecutor,
    SftpExecutor,
)
from restikls.models.run_options import RunOptions


@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        yield mock_run


@pytest.fixture
def mock_sys_platform(monkeypatch):
    def set_platform(plat: str):
        monkeypatch.setattr(sys, "platform", plat)

    return set_platform


@pytest.fixture
def mock_logger():
    with patch("flask.current_app.logger") as mock_log:
        yield mock_log


# @pytest.fixture
# def mock_urlparse(monkeypatch):
#     mock_parsed = MagicMock()
#     monkeypatch.setattr('urllib.parse.urlparse', lambda url: mock_parsed)
#     return mock_parsed


def test_local_executor_execute(mock_subprocess_run, mock_app_config):
    executor = LocalExecutor(mock_app_config)
    cmd = ["restic", "version"]
    run_options = RunOptions(capture_output=True)

    result = executor.execute(cmd, run_options)

    mock_subprocess_run.assert_called_once_with(cmd, **asdict(run_options))
    assert isinstance(result, subprocess.CompletedProcess)


def test_sftp_executor_execute_with_key(
    app, mock_subprocess_run, mock_logger, monkeypatch, sftp_config
):
    ssh_key_file = "/mock/key"
    ssh_key_content = "key content"

    mock_key_file = MagicMock()
    mock_key_file.return_value.__enter__.return_value = ssh_key_file
    monkeypatch.setattr("restikls.services.command_executor.manage_ssh_key_file", mock_key_file)
    sftp_config.ssh_key = ssh_key_content
    executor = SftpExecutor(sftp_config)
    cmd = ["restic", "version"]
    run_options = RunOptions(capture_output=True)

    result = executor.execute(cmd, run_options)
    _cmd = executor.extend_cmd_with_ssh_args(cmd, ssh_key_file)

    # Check cmd extended
    assert "-o" in _cmd
    assert "sftp.args" in "".join(_cmd)
    assert any(ssh_key_file in item for item in _cmd)
    mock_key_file.assert_called_once_with(sftp_config)
    mock_subprocess_run.assert_called_once_with(_cmd, **asdict(run_options))
    assert isinstance(result, subprocess.CompletedProcess)


def test_sftp_extend_cmd_with_ssh_args_linux(app, mock_sys_platform, mock_logger, sftp_config):
    mock_sys_platform("linux")
    sftp_config.ssh_key = None
    # sftp_config["ssh_key_file"] = "/path/to/key"
    ssh_key_file = "/path/to/key"
    executor = SftpExecutor(sftp_config)
    cmd = ["restic"]

    _cmd = executor.extend_cmd_with_ssh_args(cmd, ssh_key_file)

    assert "-o" in _cmd
    sftp_args_str = _cmd[_cmd.index("-o") + 1]
    assert ("sftp.args=" in sftp_args_str)
    assert "UserKnownHostsFile=/dev/null" in sftp_args_str


def test_sftp_extend_cmd_with_ssh_args_windows(app, mock_sys_platform, mock_logger, sftp_config):
    mock_sys_platform("win32")
    sftp_config.ssh_key = None
    ssh_key_file = "C:\\path\\to\\key"
    executor = SftpExecutor(sftp_config)
    cmd = ["restic"]

    _cmd = executor.extend_cmd_with_ssh_args(cmd, ssh_key_file)

    assert "-o" in _cmd
    sftp_args_str = _cmd[_cmd.index("-o") + 1]
    assert ("sftp.args=" in sftp_args_str)
    assert "UserKnownHostsFile=NUL" in sftp_args_str


def test_sftp_extend_cmd_no_key(app, mock_logger, mock_app_config):
    ssh_key_file = ""
    executor = SftpExecutor(mock_app_config)
    cmd = ["restic"]

    with pytest.raises(ValueError):
        executor.extend_cmd_with_ssh_args(cmd, ssh_key_file)
    # No extension if no key
    # assert len(cmd) == 1  # Unchanged


def test_restserver_parse_url_no_auth(sftp_config):
    sftp_config.repo_path = "rest:http://host/repo"
    # mock_urlparse.username = None
    # mock_urlparse.password = None

    executor = RestServerExecutor(sftp_config)

    assert not executor.is_auth_required
    assert sftp_config.repo_path == "rest:http://host/repo"  # Unchanged


def test_restserver_parse_url_with_auth(sftp_config):
    sftp_config.repo_path = "rest:http://user:pass@host:8080/repo?query=1#frag"
    # mock_urlparse.scheme = 'http'
    # mock_urlparse.username = 'user'
    # mock_urlparse.password = 'pass'
    # mock_urlparse.hostname = 'host'
    # mock_urlparse.port = 8080
    # mock_urlparse.path = '/repo'
    # mock_urlparse.query = 'query=1'
    # mock_urlparse.fragment = 'frag'

    executor = RestServerExecutor(sftp_config)

    assert executor.is_auth_required
    assert executor.rest_user == "user"
    assert executor.rest_password == "pass"
    assert executor.repo_cred.repo_path == "rest:http://host:8080/repo?query=1#frag"
    # Ensure input dataclass is not mutated
    assert sftp_config.repo_path == "rest:http://user:pass@host:8080/repo?query=1#frag"


def test_restserver_execute_no_auth(mock_subprocess_run, sftp_config):
    sftp_config.repo_path = "rest:http://host/repo"
    executor = RestServerExecutor(sftp_config)
    cmd = ["restic"]
    run_options = RunOptions(env={})

    executor.execute(cmd, run_options)

    assert "RESTIC_REST_USERNAME" not in run_options.env
    mock_subprocess_run.assert_called_once_with(cmd, **asdict(run_options))


def test_restserver_execute_with_auth(mock_subprocess_run, rest_config):
    rest_config.repo_path = "rest:http://user:pass@host/repo"
    executor = RestServerExecutor(rest_config)
    executor.is_auth_required = True
    executor.rest_user = "user"
    executor.rest_password = "pass"
    cmd = ["restic"]
    run_options = RunOptions(env={})

    executor.execute(cmd, run_options)

    assert run_options.env["RESTIC_REST_PASSWORD"] == "pass"
    assert run_options.env["RESTIC_REST_USERNAME"] == "user"
    mock_subprocess_run.assert_called_once_with(cmd, **asdict(run_options))
