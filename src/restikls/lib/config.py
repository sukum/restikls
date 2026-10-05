# File: src/restikls/lib/config.py
"""
Flask configuration module for managing restic repository settings.

Handles secure storage and retrieval of repository credentials via encrypted cookies,
environment configuration, and default settings management for the Restic backup UI.
"""

import os
import time

from flask import Response, current_app, flash, request

from ..models.credentials import ResticCredentials
from .encrypt import decrypt_repo_cred, encrypt_repo_cred


def build_environment_config(repo_path: str, repo_key: str) -> dict:
    """
    Builds the environment configuration dictionary for restic.
    Args:
        repo_path (str): Repository path
        repo_key (str): Decrypted repository key
    Returns:
        dict: Environment configuration dictionary
    """
    # Get the list from the app config, or use a sane default.
    passthrough_vars = current_app.config["REQUIRED_ENV_VARS"]
    # if current_app.debug:
    #     current_app.logger.debug("passthrough_vars: %s", passthrough_vars)

    env: dict = {_var: os.environ[_var] for _var in passthrough_vars if _var in os.environ}

    env.update(
        {
            "RESTIC_PASSWORD": repo_key,
            "RESTIC_REPOSITORY": repo_path,
        }
    )
    return env


def get_repo_cred() -> ResticCredentials | None:
    """
    Retrieves repository configuration from cookie.
    Decrypts the repository key and constructs a configuration dictionary for use.
    Validates the presence of the cookie, checks the timestamp for validity,
    and handles decryption errors.
    Added as decorator for routes that require repository configuration.
    Returns:
        ResticCredentials: The decrypted repository credentials if the cookie is present and valid. None otherwise.
    """

    if current_app.debug:
        current_app.logger.debug("get_config:route: %s", request.endpoint)
        # import inspect
        # _curr_frame = inspect.currentframe()
        # if (
        #     _curr_frame
        #     and hasattr(_curr_frame, "f_back")
        #     and _curr_frame.f_back
        #     and hasattr(_curr_frame.f_back, "f_code")
        #     and hasattr(_curr_frame.f_back.f_code, "co_name")
        # ):
        #     caller = _curr_frame.f_back.f_code.co_name
        #     current_app.logger.debug("caller: %s", caller)

    enc_repo_cred = request.cookies.get("repo_cred")
    # Debug
    # if current_app.debug:
    #     current_app.logger.debug("enc_repo_cred: %s", enc_repo_cred)

    if not enc_repo_cred:
        return None

    try:
        # Decrypt the repository credentials
        repo_cred: ResticCredentials = decrypt_repo_cred(enc_repo_cred)
        required_fields = ("repo_key", "repo_path", "timestamp")
        # Verify all expected keys present in repo_cred
        if not all(hasattr(repo_cred, k) for k in required_fields):
            current_app.logger.warning("All expected keys not found in repo_cred")
            flash("Repository credentials not all present. Contact support if it persists.", "error")
            return None
        # Validate that repo_cred timestamp is still valid
        if repo_cred.is_expired:
            current_app.logger.info(
                "Configuration expired, redirecting to config page."
            )
            flash("Session expired. Please re-enter your configuration.", "warning")
            return None

        # Load default settings and merge with session-specific data.
        return repo_cred

        # if repo_cred.ssh_key:
        #     config_data["ssh_key"] = repo_cred.ssh_key
        # Debug
        # if current_app.debug:
        #     current_app.logger.debug("config_data: %s", config_data)
        # return config_data
    except Exception as e:
        # This can happen if the cookie is invalid or the master key changed.
        current_app.logger.error(
            f"Failed to decrypt repository key or build config: {e!s}"
        )
        flash("Unexpected error with repository credentials. Contact support if it persists.", "error")
        return None

def set_config(
    response: Response, repo_path: str, repo_key: str, ssh_key: str | None
) -> Response:
    """
    Sets repository configuration into secure browser cookies.
    Args:
        response: The Flask response object to which cookies will be attached.
        repo_path (str): The path to the repository.
        repo_key (str): The secret key for the repository.
    Returns:
        The modified Flask response object.
    """
    assert repo_path and repo_key, "Both repo_path and repo_key must be provided and non-empty."
    # Determine cookie lifetime from app config or default.
    session_life = current_app.config["SESSION_LIFE"]
    enc_repo_cred: str | None = None
    try:
        # Encrypt the repository creds before setting the cookie.
        if any([repo_path, repo_key, ssh_key]):
            repo_cred = ResticCredentials(
                repo_path=repo_path or "",
                repo_key=repo_key or "",
                ssh_key=ssh_key or None,
                timestamp=time.time(),
            )
            enc_repo_cred = encrypt_repo_cred(repo_cred)
    except Exception as e:
        current_app.logger.error(f"Error setting config: encryption error: {e!s}")
        raise

    try:
        # Set secure cookies. In a production environment behind HTTPS,
        # set secure=True.
        is_secure = current_app.config.get("SESSION_COOKIE_SECURE", False)

        if enc_repo_cred:
            response.set_cookie(
                "repo_cred",
                enc_repo_cred,
                max_age=session_life,
                secure=is_secure,
                samesite="Strict",
                httponly=True,
            )
        return response
    except Exception as e:
        current_app.logger.error(f"Error setting config: set_cookie error: {e!s}")
        raise


def clear_config(response: Response) -> Response:
    """
    Removes all repository-related cookies from the response.
    Args:
        response: The Flask response object to modify.
    Returns:
        The modified Flask response object.
    """
    try:
        # Cookies should be deleted with the same path and domain attributes
        # they were set with. Assuming root path '/' and default domain.
        response.delete_cookie("repo_cred")
        return response
    except Exception as e:
        current_app.logger.error(f"Error clearing config: {e!s}")
        raise
