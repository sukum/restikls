# File: src/restikls/services/command_executor.py
"""
Command executor classes for running restic commands locally, over SFTP, or via a rest server.
Handles SSH key management and command argument construction for different repository types.
"""

import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, replace
from urllib.parse import urlparse

from flask import current_app

from ..lib.utils import manage_ssh_key_file
from ..models.credentials import ResticCredentials
from ..models.run_options import RunOptions


class CommandExecutor(ABC):
    """Abstract base class for a command executor."""
    repo_cred: ResticCredentials

    def __init__(self, repo_cred: ResticCredentials):
        self.repo_cred = repo_cred

    @abstractmethod
    def execute(
        self, cmd: list[str], run_options: RunOptions
    ) -> subprocess.CompletedProcess:
        """Executes a command using subprocess."""


class LocalExecutor(CommandExecutor):
    """Executes commands for local repositories."""

    def execute(
        self, cmd: list[str], run_options: RunOptions
    ) -> subprocess.CompletedProcess:
        # print(run_options)
        return subprocess.run(cmd, **asdict(run_options))


class SftpExecutor(CommandExecutor):
    """Executes commands for SFTP repositories, managing the SSH key."""

    def execute(
        self, cmd: list[str], run_options: RunOptions
    ) -> subprocess.CompletedProcess:
        with manage_ssh_key_file(self.repo_cred) as ssh_key_file:
            # The context manager adds 'ssh_key_file' to config, which extend_cmd_with_ssh_args uses
            _cmd = self.extend_cmd_with_ssh_args(cmd, ssh_key_file)
            return subprocess.run(_cmd, **asdict(run_options))

    def extend_cmd_with_ssh_args(
        self, cmd: list[str], ssh_key_file: str
    ) -> list[str]:
        """Extend cmd with sftp.args"""
        # Windows-specific settings
        # Use NUL instead of /dev/null
        null_device = "NUL" if sys.platform == "win32" else "/dev/null"
        sftp_args = [
            "-T",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={null_device}",
        ]
        if current_app.config.get("DEBUG_SSH_CONNECTION", False):
            sftp_args.append("-vv")

        _cmd = cmd.copy()
        # SSH Key file
        # get ssh_key_file from config
        # if not ssh_key_file:
        #     ssh_key_file = self.config.get("ssh_key_file")
        current_app.logger.debug("ssh_key_file: %s", ssh_key_file)
        if ssh_key_file:
            sftp_args.extend(["-i", self._quote_restic_arg(ssh_key_file)])
            sftp_args_str = " ".join(sftp_args)
            current_app.logger.debug("sftp_args_str: %s", sftp_args_str)
            _cmd.extend(["-o", f"sftp.args={sftp_args_str}"])
        else:
            raise ValueError("invalid value for ssh key file passed in")
        current_app.logger.debug("cmd: %s", _cmd)
        return _cmd

    @staticmethod
    def _quote_restic_arg(value: str) -> str:
        # Restic accepts either quote style and removes the surrounding quotes.
        for quote in ('"', "'"):
            if quote not in value and not value.endswith("\\"):
                return f"{quote}{value}{quote}"

        raise ValueError("SSH key path cannot be quoted for sftp.args")

class RestServerExecutor(CommandExecutor):
    """Executes commands for restic rest server repositories."""

    __slots__ = ("is_auth_required", "repo_cred", "rest_password", "rest_user")

    def __init__(self, repo_cred: ResticCredentials):
        clean_repo_path, self.rest_user, self.rest_password = (
            self.parse_restic_rest_url(repo_cred.repo_path)
        )
        super().__init__(replace(repo_cred, repo_path=clean_repo_path))
        self.is_auth_required = bool(self.rest_user and self.rest_password)

    @staticmethod
    def parse_restic_rest_url(
        repo_path: str,
    ) -> tuple[str, str | None, str | None]:
        """Return the clean REST URL and any authentication credentials it contains."""
        assert repo_path.startswith("rest:http")

        # If rest authentication present
        if "@" in repo_path:
            # strip rest: from the url start
            url = repo_path[5:]
            # Parse the URL to extract components
            parsed = urlparse(url)

            # Extract username and password from URL if present
            if parsed.username and parsed.password:
                # Reconstruct URL without credentials for security
                netloc = parsed.hostname if parsed.hostname else ""
                if ":" in netloc and not netloc.startswith("["):
                    netloc = f"[{netloc}]"
                if parsed.port:
                    netloc += f":{parsed.port}"

                clean_url = parsed._replace(netloc=netloc).geturl()
                return f"rest:{clean_url}", parsed.username, parsed.password

        return repo_path, None, None

    def execute(
        self, cmd: list[str], run_options: RunOptions
    ) -> subprocess.CompletedProcess:
        """Execute command with REST server authentication if required."""
        if self.is_auth_required:
            run_options.env.update(
                {
                    "RESTIC_REST_PASSWORD": self.rest_password,
                    "RESTIC_REST_USERNAME": self.rest_user,
                }
            )
        return subprocess.run(cmd, **asdict(run_options))
