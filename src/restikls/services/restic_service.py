# File: src/restikls/services/restic_service.py
"""
Service layer for orchestrating restic backup commands, handling execution,
caching, error handling, and JSON parsing for repository operations.
"""

import json
import shlex
import subprocess
from collections.abc import Callable
from typing import Any, TypeVar, cast

from flask import current_app

from ..lib.exceptions import (
    FileAccessError,
    KeyNotFoundError,
    ResticServiceError,
    ResticTimeoutError,
    ResticValidationError,
    SnapshotNotFoundError,
)
from ..lib.utils import combine_json_lines, time_process
from ..models.credentials import ResticCredentials
from ..models.restic_json import (
    FileHistoryPayload,
    FileMatchPayload,
    KeyPayload,
    NodePayload,
    RepoCheckPayload,
    RepoStatsPayload,
    SnapshotHeaderPayload,
    SnapshotPayload,
    parse_check,
    parse_file_history,
    parse_keys,
    parse_repo_stats,
    parse_snapshot,
    parse_snapshot_files_raw,
    parse_snapshots,
)
from ..models.run_options import RunOptions
from .cache_service import CacheService
from .command_builder import ResticCommandBuilder
from .command_executor import CommandExecutor

T = TypeVar("T")


class ResticService:
    """
    Service for orchestrating restic commands via a command executor.
    """

    def __init__(
        self, repo_cred: ResticCredentials, cache_service: CacheService, executor: CommandExecutor
    ):
        self.cache_service: CacheService = cache_service
        self.repo_cred: ResticCredentials = repo_cred
        self.executor: CommandExecutor = executor
        if current_app.debug:
            current_app.logger.debug("ResticService initialized")

    def _execute_restic_json_cmd(
        self,
        cmd: list[str],
        run_options: RunOptions,
        error_context: str,
        cache_key: str | None = None,
        json_preprocessor: Callable[[str], str] | None = None,
        parser: Callable[[Any], T] | None = None,
    ) -> T:
        """
        Executes a restic command that returns JSON,
        handling caching and error parsing.

        Args:
            cmd: The command to execute as a list of strings.
            run_options: Options for subprocess.run.
            error_context: A string describing the operation for error messages (e.g., "snapshots").
            cache_key: The key for caching. If None, caching is skipped.
            json_preprocessor: A function to run on the stdout bytes before JSON decoding.
            parser: An optional validation function that verifies the decoded JSON structure.

        Returns:
            The parsed and validated JSON data.

        Raises:
            subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError, ResticValidationError
        """
        if cache_key and self.cache_service.has(cache_key):
            return cast(T, self.cache_service.get(cache_key))

        result = None
        try:
            result = self.executor.execute(cmd, run_options)
            result.check_returncode()
            self.log_stderr(result, error_context)

            output_for_json = result.stdout
            if json_preprocessor:
                # E.g., combine_json_lines takes bytes and returns a string for json.loads
                output_for_json = json_preprocessor(output_for_json)

            data = json.loads(output_for_json)

            if parser is not None:
                data = parser(data)

            if cache_key:
                self.cache_service.set(cache_key, data)

            return cast(T, data)
        except ResticValidationError as e:
            current_app.logger.error(
                f"Validation failed for {error_context} output: {e!s}"
            )
            current_app.logger.error("cmd: %s", cmd)
            if result:
                current_app.logger.error("stdout: %s", result.stdout)
                self.log_stderr(result, error_context)
            raise
        except subprocess.TimeoutExpired as e:
            current_app.logger.error(
                f"Restic {error_context} command timed out: {' '.join(cmd)}"
            )
            current_app.logger.error(str(e))
            self.log_stderr(result, error_context)
            raise ResticTimeoutError(
                "The operation timed out. The repository might be busy or on a slow network."
            ) from e
        except subprocess.CalledProcessError as e:
            current_app.logger.error(
                f"Command failed with exit code {e.returncode}: {' '.join(e.cmd)}"
            )
            if result:
                current_app.logger.error("stdout: %s", result.stdout)
                self.log_stderr(result, error_context)
            raise ResticServiceError(
                f"The '{error_context}' operation failed. Please check the logs for details."
            ) from e
        except json.JSONDecodeError as e:
            current_app.logger.error(
                f"Error decoding JSON for {error_context}: {e!s}"
            )
            current_app.logger.error("cmd: %s", cmd)
            if result:
                current_app.logger.error("stdout: %s", result.stdout)
                self.log_stderr(result, error_context)
            raise ValueError(f"Could not parse {error_context} output.") from e

    @time_process(threshold=15)
    def get_snapshots(
        self, filters: dict[str, Any] | None = None
    ) -> list[SnapshotPayload]:
        """
        Retrieve snapshots with optional filters.
        """
        filters = filters or {}
        tags = shlex.split(filters.get("tags", "")) if filters.get("tags") else []
        hosts = shlex.split(filters.get("hosts", "")) if filters.get("hosts") else []
        sort = filters.get("sort", "desc")

        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.snapshots(tags=tags, hosts=hosts)
        cache_key = self.cache_service.generate_key(spec.argv)

        snapshots = self._execute_restic_json_cmd(
            spec.argv, spec.run_options, "snapshots", cache_key, parser=parse_snapshots
        )

        snapshots.sort(key=lambda x: x["time"], reverse=(sort == "desc"))
        return snapshots


    @time_process(threshold=15)
    def get_snapshot(self, snapshot_id: str) -> list[SnapshotPayload]:
        """
        Retrieve a specific snapshot with given id
        """
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.snapshot(snapshot_id=snapshot_id)
        cache_key = self.cache_service.generate_key(spec.argv)
        snapshots = self._execute_restic_json_cmd(
            spec.argv, spec.run_options, "snapshots", cache_key, parser=parse_snapshot
        )
        return snapshots

    @time_process(threshold=20)
    def get_snapshot_files(
        self, snapshot_id: str
    ) -> tuple[SnapshotHeaderPayload, list[NodePayload]]:
        """
        Retrieve files for a specific snapshot.
        """
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.ls(snapshot_id)
        spec.run_options.timeout = current_app.config["FILE_OPERATIONS_TIMEOUT"]
        cache_key = self.cache_service.generate_key(spec.argv)

        files = self._execute_restic_json_cmd(
            spec.argv,
            spec.run_options,
            error_context="ls",
            cache_key=cache_key,
            json_preprocessor=combine_json_lines,
            parser=parse_snapshot_files_raw,
        )
        if not files:
            raise SnapshotNotFoundError(snapshot_id)
        header = cast(SnapshotHeaderPayload, files[0])
        file_list = cast(list[NodePayload], files[1:])
        return header, file_list


    def file_metadata(self, snapshot_id: str, file_path: str) -> FileMatchPayload:
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.file_metadata(snapshot_id, file_path)
        cache_key = self.cache_service.generate_key(spec.argv)

        if self.cache_service.has(cache_key):
            return cast(FileMatchPayload, self.cache_service.get(cache_key))

        err_message = (
            f"Failed finding metadata for file: {file_path} in snapshot: #{snapshot_id}"
        )
        # Do not cache since the result has to be returned unwrapped
        try:
            files = self._execute_restic_json_cmd(
                spec.argv,
                spec.run_options,
                "find",
                None,
                parser=parse_file_history,
            )
            if not files or not files[0].get("matches"):
                raise FileAccessError(err_message)
            metadata = files[0]["matches"][0]
            # find can return dir and file
            if metadata["type"] != "file":
                raise FileAccessError(f"Expected file, got a directory for path {file_path}")
            else: # cast as file
                metadata = cast(FileMatchPayload, metadata)
            self.cache_service.set(cache_key, metadata)
            return metadata
        except (ResticServiceError, ValueError, IndexError, KeyError) as e:
            raise FileAccessError(err_message) from e

    def dump_file(self, snapshot_id: str, file_path: str) -> bytes:
        """
        Dump a file from a specific snapshot.
        """
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.dump(snapshot_id, file_path)

        try:
            result = self.executor.execute(spec.argv, spec.run_options)
            result.check_returncode()
            if result.stderr:
                stderr_txt = result.stderr.decode("utf-8")
                current_app.logger.error(f"Stderr from 'restic dump': {stderr_txt}")
            return result.stdout
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            error_message = (
                e.stderr.decode()
                if hasattr(e, "stderr") and e.stderr
                else "Could not dump file."
            )
            current_app.logger.error(f"Restic dump failed: {error_message}")
            raise FileAccessError(error_message) from e
        except Exception as e:
            current_app.logger.exception("An unexpected error occurred in dump_file.")
            raise ResticServiceError(
                "An unexpected internal error occurred while retrieving the file."
            ) from e

    def get_file_history(
        self, file_path: str, paths: list[str]
    ) -> list[FileHistoryPayload]:
        """
        Retrieve file history for a specific file path.
        """
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.find(file_path, paths)
        cache_key = self.cache_service.generate_key(spec.argv)

        return self._execute_restic_json_cmd(
            spec.argv, spec.run_options, "find", cache_key, parser=parse_file_history
        )

    def get_keys(self) -> list[KeyPayload]:
        """
        Retrieve list of repository encryption keys.
        """
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.key_list()
        cache_key = self.cache_service.generate_key(spec.argv)

        return self._execute_restic_json_cmd(
            spec.argv, spec.run_options, "key list", cache_key, parser=parse_keys
        )

    def get_key(self, key_id: str) -> KeyPayload:
        """
        Retrieve details for a specific repository key.
        """
        keys = self.get_keys()
        key = next((k for k in keys if k["id"] == key_id), None)
        if not key:
            raise KeyNotFoundError(key_id)
            
        return key

    def get_repo_stats(self) -> RepoStatsPayload:
        """
        Get repository storage statistics.
        """
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.stats()
        cache_key = self.cache_service.generate_key(spec.argv)

        return self._execute_restic_json_cmd(
            spec.argv, spec.run_options, "stats", cache_key, parser=parse_repo_stats
        )

    def check(self) -> RepoCheckPayload:
        """
        Perform repository integrity check.
        """
        builder = ResticCommandBuilder(self.repo_cred)
        spec = builder.check()

        return self._execute_restic_json_cmd(
            spec.argv,
            spec.run_options,
            error_context="check",
            cache_key=None,  # No caching for this operation
            parser=parse_check,
        )

    def log_stderr(
        self, result: subprocess.CompletedProcess | None, error_context: str
    ) -> None:
        """
        If a command execution prints anything to stderr, log it
        """
        if result and result.stderr:
            stderr_str = (
                result.stderr
                if isinstance(result.stderr, str)
                else result.stderr.decode("utf-8", "ignore")
            )
            if stderr_str:
                current_app.logger.error(
                    f"Stderr from 'restic {error_context}': {stderr_str}"
                )
