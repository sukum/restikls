# File: src/restikls/lib/encrypt.py
"""
Encryption utilities for handling repository keys securely using Fernet encryption.
Provides functions for key generation, encryption, and decryption.
"""

import json
import logging
import os
import sys
from dataclasses import asdict
from typing import Any

from cryptography.fernet import Fernet
from flask import current_app, has_app_context

from ..models import credentials

cipher: Fernet | None = None


def _get_logger() -> logging.Logger:
    if has_app_context():
        return current_app.logger
    return logging.getLogger("restikls")


def generate_new_key(key_file_path: str, is_cli: bool = False) -> bytes:
    """
    Generates a new Fernet encryption key and saves it to the specified file.
    Based on whether command line or web app, it logs to print or logger
    Args:
        key_file_path (str): The path to the file where the key will be saved.
        is_cli (bool): If True, called from command line.
    Returns:
        str/bool: key if the key was successfully generated and saved, False otherwise.
    """

    # log_error = print if is_cli else current_app.logger.warning
    # log_info = print if is_cli else current_app.logger.info
    # fd = {'file': sys.stderr} if is_cli else {}

    try:
        _get_logger().info(
            f"Generating new encryption key at '{key_file_path}'..."
        )
        encryption_key = Fernet.generate_key()
        with open(key_file_path, "wb") as f:
            f.write(encryption_key)
        # Set file permissions for security (readable only by owner)
        if sys.platform != "win32":
            os.chmod(key_file_path, 0o600)
        _get_logger().info("New encryption key successfully generated and saved.")
        _get_logger().info(
            f"Permissions for '{key_file_path}' set to 600 (read/write for owner only)."
        )
        return encryption_key
    except (OSError) as e:
        _get_logger().warning(
            f"ERROR: Could not write key to '{key_file_path}': {e}"
        )
        raise RuntimeError(
            "Generated Fernet encryption key could not be written to file."
        ) from e
    except Exception as e:
        _get_logger().warning(
            f"Failed to generate fernet encryption key to {key_file_path}"
        )
        _get_logger().warning(e)
        raise RuntimeError("Fernet encryption key generation failed.") from e


def read_key(key_file_path: str) -> bytes:
    """Reads the encryption key from the secret.key file"""
    try:
        with open(key_file_path, "rb") as f:
            encryption_key = f.read()
        return encryption_key
    except (OSError) as e:
        _get_logger().error(
            f"Error reading secret key file '{key_file_path}': {e}"
        )
        raise RuntimeError("Error reading secret key file.") from e
    except Exception as e:
        _get_logger().error(f"Secret key read failed: {e}")
        raise RuntimeError("Secret key read failed.") from e


def init_cipher() -> None:
    """
    Initializes the global Fernet cipher instance.

    It loads an encryption key from the file specified by 'KEY_FILE' in the app config.
    If the file doesn't exist, it generates a new key and saves it.
    Ensures the 'cipher' global variable is available for encryption and decryption tasks.
    Raises:
        RuntimeError: If there's an error reading/writing the key file or initializing the cipher.
    """
    global cipher
    if cipher:
        return

    # Use the app config value for KEY_FILE, or fall back to the default.
    key_file_path = current_app.config["KEY_FILE"]

    try:
        # Generate a new encryption key if the key file doesn't exist.
        if not os.path.exists(key_file_path):
            encryption_key = generate_new_key(key_file_path)
        else:
            encryption_key = read_key(key_file_path)

        if not encryption_key:
            raise RuntimeError("Encryption key is invalid.")
        cipher = Fernet(encryption_key)
    except (OSError) as e:
        current_app.logger.error(
            f"Error reading secret key file '{key_file_path}': {e}"
        )
        raise RuntimeError("Failed to load the secret key.") from e
    except Exception as e:
        current_app.logger.error(f"Failed to initialize the cipher: {e}")
        raise RuntimeError("Cipher initialization failed.") from e


def decrypt_repo_cred(encrypted_repo_cred: str) -> credentials.ResticCredentials:
    """
    Decrypts the encrypted repository cred using the cipher.
    Args:
        encrypted_repo_cred (str): The encrypted repository cred from the cookie
    Returns:
        credentials.ResticCredentials: The decrypted repository cred
    Raises:
        Exception: If decryption fails
    """
    # Ensure the cipher is ready for decryption.
    init_cipher()

    try:
        if cipher is None:
            raise RuntimeError("Cipher not initialized.")
        repo_cred_bytes = cipher.decrypt(encrypted_repo_cred.encode())
        repo_cred_dict: dict[str, Any] = json.loads(repo_cred_bytes.decode())

        return credentials.ResticCredentials(**repo_cred_dict)  # type: ignore[missing-argument]
    except TypeError as e:
        current_app.logger.error(
            f"Required repo credential fields missing in config cookie: {e}"
        )
        raise RuntimeError("Repo credentials decryption failed.") from e
    except Exception as e:
        current_app.logger.error(f"Failed to decrypt the repo credentials: {e}")
        raise RuntimeError("Repo credentials decryption failed.") from e


def encrypt_repo_cred(repo_cred: credentials.ResticCredentials) -> str:
    """
    Encrypts the repository cred using the cipher.
    Args:
        repo_cred (credentials.ResticCredentials): The repository cred provided by user
    Returns:
        str: The encrypted repository cred
    Raises:
        Exception: If decryption fails
    """
    # Ensure the cipher is ready for encryption.
    init_cipher()

    try:
        if cipher is None:
            raise RuntimeError("Cipher not initialized.")
        repo_cred_str = json.dumps(asdict(repo_cred), separators=(",", ":")).encode()
        repo_cred_bytes = cipher.encrypt(repo_cred_str)
        return repo_cred_bytes.decode()
    except Exception as e:
        current_app.logger.error(f"Failed to encrypt the repo credentials: {e}")
        raise RuntimeError("Repo credentials encryption failed.") from e
