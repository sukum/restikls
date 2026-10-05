# File: src/restikls/services/command_builder.py
"""
Module for building restic CLI commands for various repository operations.
"""

import dataclasses
from dataclasses import dataclass
from typing import Any

from flask import current_app

from ..lib.config import build_environment_config
from ..models.credentials import ResticCredentials
from ..models.run_options import RunOptions


@dataclass
class CommandSpec:
    """Specification for a built restic command and its execution options."""

    argv: list[str]
    run_options: RunOptions


class ResticCommandBuilder:
    """
    Builder for constructing restic commands.
    """
    
    __slots__ = ("cmd", "repo_cred", "run_options")

    def __init__(self, repo_cred: ResticCredentials):
        """Initialize the command builder with repository credentials."""
        self.repo_cred: ResticCredentials = repo_cred
        # self.run_options: dict[str, Any] = deepcopy(config["run_options"])
        # subprocess run
        self.run_options: RunOptions = RunOptions(
            timeout=current_app.config["SUBPROCESS_TIMEOUT"],
            env=build_environment_config(
                repo_cred.repo_path, 
                repo_cred.repo_key 
            )
        )
        # self.run_options: dict[str, Any] = {
        #     "capture_output": True,
        #     "text": True,
        #     "shell": False,  # Important for security
        #     "timeout": current_app.config["SUBPROCESS_TIMEOUT"],
        #     "check": False,  # We check return code manually
        # }
        # self.run_options['env'] = build_environment_config(
        #     config["repo_cred"].repo_path, 
        #     config["repo_cred"].repo_key 
        # )
        self.cmd: list[str] = []

    def _cmd_post_processing(self, cmd: list[str]):
        """Post process built command to extend it."""
        if current_app.debug:
            current_app.logger.debug("cmd: %s", cmd)
            # current_app.logger.debug("run_options: %s", self.run_options)

    def snapshots(
        self, tags: list[str] | None = None, hosts: list[str] | None = None
    ) -> CommandSpec:
        """
        Build command for listing snapshots.
        """
        cmd = ["restic", "snapshots", "--json"]

        tags = tags or []
        hosts = hosts or []

        for tag in tags:
            cmd.extend(["--tag", tag])
        for host in hosts:
            cmd.extend(["--host", host])
        self._cmd_post_processing(cmd)
        # run_options = dataclasses.replace(self.run_options)
        run_options = _copy_run_options(self.run_options)
        return CommandSpec(argv=cmd, run_options=run_options)

    def snapshot(self, snapshot_id: str) -> CommandSpec:
        """
        Build command for snapshot details.
        """
        cmd = ["restic", "snapshots", "--json", "--", snapshot_id]
        self._cmd_post_processing(cmd)
        # run_options = dataclasses.replace(self.run_options)
        run_options = _copy_run_options(self.run_options)
        return CommandSpec(argv=cmd, run_options=run_options)

    def ls(self, snapshot_id: str) -> CommandSpec:
        """
        Build command for listing files in a snapshot.
        """
        # No rustic equivalent for 'find'
        cmd = ["restic", "ls", "--json", "--", snapshot_id]
        self._cmd_post_processing(cmd)
        # run_options = dataclasses.replace(self.run_options)
        run_options = _copy_run_options(self.run_options)
        return CommandSpec(argv=cmd, run_options=run_options)

    def find(
        self, file_path: str, paths: list[str]
    ) -> CommandSpec:
        """
        Build command for retrieving file history for a specific file path.
        """
        # No rustic equivalent for 'find'
        cmd = ["restic", "find", "--quiet", "--json"]
        for path in paths:
            cmd.extend(["--path", path])
        cmd.extend(["--", file_path])
        self._cmd_post_processing(cmd)

        # run_options = dataclasses.replace(self.run_options)
        run_options = _copy_run_options(self.run_options)
        return CommandSpec(argv=cmd, run_options=run_options)

    def file_metadata(
        self, snapshot_id: str, file_path: str
    ) -> CommandSpec:
        cmd = [
            "restic",
            "find",
            "--quiet",
            "--json",
            "--snapshot",
            snapshot_id,
            "--",
            file_path,
        ]
        self._cmd_post_processing(cmd)

        # run_options = dataclasses.replace(self.run_options, text = False)
        run_options = _copy_run_options(self.run_options, text = False)
        return CommandSpec(argv=cmd, run_options=run_options)

    def dump(
        self, snapshot_id: str, file_path: str
    ) -> CommandSpec:
        """
        Build command for dumping a file from a snapshot.
        """
        cmd = ["restic", "dump", "--quiet", "--", snapshot_id, file_path]
        self._cmd_post_processing(cmd)

        # run_options = dataclasses.replace(
        #     self.run_options,
        #     text = False, timeout=current_app.config["FILE_OPERATIONS_TIMEOUT"]
        # )
        run_options = _copy_run_options(self.run_options, text = False, timeout=current_app.config["FILE_OPERATIONS_TIMEOUT"])
        return CommandSpec(argv=cmd, run_options=run_options)

    def stats(self, mode: str = "raw-data") -> CommandSpec:
        """
        Build command for repository statistics.
        """
        cmd = ["restic", "stats", "--mode", mode, "--json"]
        # run_options = dataclasses.replace(
        #     self.run_options, timeout=current_app.config["REPO_STATS_TIMEOUT"]
        # )
        run_options = _copy_run_options(self.run_options, timeout=current_app.config["REPO_STATS_TIMEOUT"])
        self._cmd_post_processing(cmd)
        return CommandSpec(argv=cmd, run_options=run_options)

    def key_list(self) -> CommandSpec:
        """
        Build command for listing repository keys.
        """
        # No rustic equivalent for 'key list'
        cmd = ["restic", "key", "list", "--json"]
        self._cmd_post_processing(cmd)
        # run_options = dataclasses.replace(self.run_options)
        run_options = _copy_run_options(self.run_options)
        return CommandSpec(argv=cmd, run_options=run_options)

    def check(self) -> CommandSpec:
        """
        Build command for checking repository.
        """
        # No rustic equivalent for 'key list'
        cmd = ["restic", "check", "--json"]
        self._cmd_post_processing(cmd)
        # run_options = dataclasses.replace(
        #     self.run_options,
        #     timeout = current_app.config["MAINTENANCE_CHECK_TIMEOUT"]
        # )
        run_options = _copy_run_options(self.run_options, timeout=current_app.config["MAINTENANCE_CHECK_TIMEOUT"])
        return CommandSpec(argv=cmd, run_options=run_options)

    def validate_repository(self) -> CommandSpec:
        """
        Validates that a repository exists at the given path and is accessible with the given key.
        It runs a lightweight command (`snapshots --no-lock`) to verify credentials.
        """
        cmd = ["restic", "snapshots", "latest", "--no-lock", "--json"]
        self._cmd_post_processing(cmd)
        # run_options = dataclasses.replace(self.run_options)
        run_options = _copy_run_options(self.run_options)
        return CommandSpec(argv=cmd, run_options=run_options)

def _copy_run_options(run_options, **changes: Any) -> RunOptions:
    return dataclasses.replace(
        run_options,
        env=run_options.env.copy(), # make a copy of env for each shallow dataclass.replace
        **changes,
    )
