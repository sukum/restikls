# File: src/restikls/models/backends.py

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from flask import current_app


class BackendType(str, Enum):
    LOCAL = "local"
    SFTP = "sftp"
    REST = "rest"


@dataclass
class BackendInput:
    repo_path: str
    repo_key: str = ""
    ssh_key: str | None = None


def determine_backend_type(repo_path: str) -> BackendType:
    """
    Determine the BackendType from the repository path prefix.
    """
    if repo_path.startswith("sftp://"):
        return BackendType.SFTP
    if repo_path.startswith("rest:http"):
        return BackendType.REST
    return BackendType.LOCAL


@dataclass
class BaseBackend(ABC):
    repo_path: str
    repo_key: str

    @property
    def backend_type(self) -> BackendType:
        return BackendType.LOCAL

    def validate(self) -> None:
        """
        Unified validation executor. 
        Automatically calls all methods in the class that start with 'validate_'.
        """
        self.validate_path()
        self.validate_key()

    def validate_path(self) -> None:
        if not self.repo_path:
            msg = "Repository path cannot be empty."
            current_app.logger.error(msg)
            raise ValueError(msg)
        if "\0" in self.repo_path:  # Block Null Bytes
            msg = "Null byte detected in repo path"
            current_app.logger.error(msg)
            raise ValueError(msg)
    
    def validate_key(self) -> None:
        if not self.repo_key:
            msg = "Repository key cannot be empty."
            current_app.logger.error(msg)
            raise ValueError(msg)
        if len(self.repo_key) > current_app.config["REPO_KEY_MAXLEN"]:
            msg = (
                f"Repo key length exceeds allowed maximum length of \
                    {current_app.config['REPO_KEY_MAXLEN']}"
            )
            current_app.logger.error(msg)
            raise ValueError(msg)

@dataclass
class LocalBackend(BaseBackend):

    def validate_path(self) -> None:
        super().validate_path()
        # Additional validation for local paths
        # Get base dir from config
        repo_base_dir_config = current_app.config["REPO_BASE_DIR"]
        # Resolve it to an absolute path
        base_path = Path(repo_base_dir_config).resolve()

        if not Path(self.repo_path).is_absolute():
            # Join the repo_path with the base directory
            # _subdir = self.repo_path.lstrip(os.sep) # strip leading '/'
            repo_base_dir = (base_path / self.repo_path).resolve() # prepend base dir to repo_path
        else:
            repo_base_dir = Path(self.repo_path).resolve()

        # Prevent Directory Traversal
        # Check if the user supplied repo path is inside the configured REPO_BASE_DIR
        if not repo_base_dir.is_relative_to(base_path) or repo_base_dir == base_path:
            msg = f"User supplied path '{self.repo_path}' "\
                  f"not within base dir '{repo_base_dir_config}'"
            current_app.logger.warning(msg)
            raise ValueError(msg)
            
        # Check existence of path
        if not repo_base_dir.exists():
            msg = f"Path '{repo_base_dir}' does not exist"
            current_app.logger.warning(msg)
            raise ValueError(msg)
            
        # Check if directory
        if not repo_base_dir.is_dir():
            msg = f"Path '{repo_base_dir}' is not a directory"
            current_app.logger.warning(msg)
            raise ValueError(msg)


@dataclass
class SFTPBackend(BaseBackend):
    ssh_key: str | None = None

    def __post_init__(self) -> None:
        """
        Runs automatically after __init__. 
        We use this to sanitize inputs before any validation occurs.
        """
        if isinstance(self.ssh_key, str) and self.ssh_key:
            # Strip invisible/invalid unicode chars from pasted keys
            self.ssh_key = self.ssh_key.encode("ascii", "ignore").decode("ascii").strip()

    @property
    def backend_type(self) -> BackendType:
        return BackendType.SFTP

    def validate(self) -> None:
        super().validate()
        self.validate_ssh_key()

    def validate_path(self) -> None:
        super().validate_path()
        if not self.repo_path.startswith("sftp://"):
            msg = "SFTP paths must start with 'sftp://'."
            current_app.logger.error(
                "%s. Got %s instead.",
                msg,
                self.repo_path
            )
            raise ValueError(msg)

    def validate_ssh_key(self) -> None:
        if not self.ssh_key:
            msg = "SSH key is required for SFTP repositories."
            current_app.logger.error(msg)
            raise ValueError(msg)
        # A very basic check for PEM-encoded private keys.
        # This covers RSA, ECDSA, ED25519, and OpenSSH formats.
        cleaned_key = self.ssh_key.strip()
        if not(
            cleaned_key.startswith("-----BEGIN")
            and "PRIVATE KEY" in cleaned_key
        ):
            msg = "Invalid SSH key format. Expected a PEM-encoded private key."
            current_app.logger.error(msg)
            raise ValueError(msg)

@dataclass
class RESTBackend(BaseBackend):

    @property
    def backend_type(self) -> BackendType:
        return BackendType.REST

    def validate_path(self) -> None:
        super().validate_path()
        if not self.repo_path.startswith("rest:http"):
            msg = "RestServer paths must start with 'rest:http'."
            current_app.logger.error(
                "%s. Got %s instead.",
                msg,
                self.repo_path
            )
            raise ValueError(msg)

def get_repo_scheme(
    backend_input: BackendInput
) -> BaseBackend:
    """
    Factory function to infer the correct restic backend scheme from the repo_path.
    Expects a BackendInput instance or explicit kwargs: repo_path, repo_key, and optionally ssh_key.
    """
    assert isinstance(backend_input, BackendInput)
    path = backend_input.repo_path
    key = backend_input.repo_key
    ssh = backend_input.ssh_key

    backend_type = determine_backend_type(path)

    if not path:
        # Fallback to base to trigger the empty path validation error nicely
        return LocalBackend(repo_path=path, repo_key=key)

    # if path starts with sftp://, use SFTPBackend
    if backend_type == BackendType.SFTP:
        return SFTPBackend(
            repo_path=path,
            repo_key=key,
            ssh_key=ssh,
        )
    # if path starts with rest:http, use RESTBackend
    elif backend_type == BackendType.REST:
        return RESTBackend(
            repo_path=path,
            repo_key=key,
        )
    # if no matching prefix, default to LocalBackend
    else:
        # Defaults to local if no specific protocol is prefixed
        return LocalBackend(
            repo_path=path,
            repo_key=key,
        )
