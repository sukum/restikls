# File: src/restikls/services/validator_service.py
"""
Service for validating restic repositories before full configuration.
"""

from typing import NamedTuple
import subprocess
import time

from flask import current_app

from ..lib.dummy_cache import DummyCache
from ..models import credentials
from .cache_service import CacheService
from .command_builder import CommandSpec, ResticCommandBuilder
from .factory import ResticServiceFactory

class ValidationResult(NamedTuple):
    success: bool
    error_message: str | None

# --- Standalone Validation Function ---
def repository(
    repo_path: str, repo_key: str, ssh_key: str | None
) -> ValidationResult:
    """
    Validate repository at repo_path and having repo_key.
    This is a standalone function for use before a full config/service object is created.
    Args:
            repo_path (str): The absolute path to the repository.
            repo_key (str): The repository access key.
            ssh_key (str): The ssh key.
    Returns:
        A ValidationResult object containing:
        - success (bool): True if validation is successful, False otherwise.
        - error_message (str | None): An error message if validation fails, otherwise None.
    """
    result = None
    cmd = None
    try:
        # config = dict()
        # Important to identify if sftp or local
        # config["repo_path"] = repo_path
        # config["ssh_key"] = ssh_key
        repo_cred = credentials.ResticCredentials(
            repo_path=repo_path or "",
            repo_key=repo_key or "",
            ssh_key=ssh_key or None,
            timestamp=time.time(),
        )
        # config["repo_cred"] = repo_cred
        # env = build_environment_config(repo_path, repo_key)
        # rest_debug_file = (tempfile.gettempdir()+"/restic.log").replace("\\", "/")
        # env['DEBUG_LOG'] = rest_debug_file
        # config["run_options"]["env"] = env
        cache = DummyCache()
        cache_service = CacheService(cache)
        restic_service = ResticServiceFactory.get_service(repo_cred, cache_service)
        builder = ResticCommandBuilder(restic_service.repo_cred)
        spec = builder.validate_repository()
        cmd = spec.argv
        result = restic_service.executor.execute(spec.argv, spec.run_options)
        result.check_returncode()
        if result.stderr:
            current_app.logger.warning(f"Stderr from '{cmd} ': {result.stderr}")
        current_app.logger.debug(f"Stdout from '{cmd} ': {result.stdout}")
        current_app.logger.info(f"Successfully validated repository '{repo_path}'.")
        return ValidationResult(success=True, error_message=None)
    except subprocess.TimeoutExpired:
        msg = (
            "Validation timed out. The repository might be on a slow network or locked."
        )
        current_app.logger.error(f"{msg} (Repo: '{repo_path}')")
        return ValidationResult(success=False, error_message=msg)
    except subprocess.CalledProcessError as e:
        if result:
            stderr = result.stderr.lower()
            current_app.logger.info(f"Stdout from '{cmd} ': {result.stdout}")
            current_app.logger.error(
                f"Failed to validate repository '{repo_path}'. "
                f"Return code: {result.returncode}, Stderr: {result.stderr.strip()}"
                f"Stdout: {result.stdout.strip()}"
            )
            if "password incorrect" in stderr or "authentication failed" in stderr:
                return ValidationResult(success=False, error_message="Invalid repository key: Authentication failed.")
            if "is not a repository" in stderr:
                return ValidationResult(success=False, error_message="The specified path is not a valid repository.")
            # Generic error for other issues (e.g., permissions, corruption)
            return ValidationResult(
                success=False,
                error_message=f"Could not access the repository. Please check path and permissions.\
                            Error: {stderr.strip()}",
            )
        else:
            current_app.logger.exception(
                "An unexpected error occurred during subprocess.run for repository validation"
            )
            current_app.logger.exception(e)
            return ValidationResult(success=False, error_message=f"An unexpected error occurred: {e}")

    except FileNotFoundError as e:
        cmd_name = e.filename if e.filename else "restic"
        current_app.logger.error(
            f"Command '{cmd_name}' not found. Make sure it is installed \
                                 and in the system's PATH."
        )
        return ValidationResult(
            False,
            f"Executable '{cmd_name}' not found. Is it installed and in your PATH?",
        )
    except Exception as e:
        current_app.logger.exception(
            f"An unexpected error occurred during validation: {e}"
        )
        return ValidationResult(False, f"An unexpected error occurred: {e}")
