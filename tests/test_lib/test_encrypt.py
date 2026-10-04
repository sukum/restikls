# File: tests/test_lib/test_encrypt.py

import logging
import os
import sys
import time
from unittest.mock import MagicMock, mock_open, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from restikls.lib import encrypt
from restikls.models import credentials


@pytest.fixture(autouse=True)
def reset_cipher(monkeypatch):
    """Fixture to reset the global cipher object before each test."""
    monkeypatch.setattr(encrypt, "cipher", None)


def test_generate_new_key_success(app, tmp_path):
    """Test successful generation of a new key."""
    key_file = tmp_path / "secret.key"
    with app.app_context():
        with patch("os.chmod") as mock_chmod:
            mock_logger = MagicMock()
            app.logger = mock_logger

            key = encrypt.generate_new_key(str(key_file))

            assert key is not False
            assert len(key) > 30  # Fernet keys are base64 encoded
            assert key_file.exists()
            if sys.platform != "win32":
                mock_chmod.assert_called_once_with(str(key_file), 0o600)
            mock_logger.info.assert_any_call(
                f"Generating new encryption key at '{key_file}'..."
            )


def test_generate_new_key_io_error(app, monkeypatch, caplog):
    """Test key generation failure due to an IO/OS error."""
    with app.app_context():
        caplog.set_level(logging.WARNING)
        # Mock open to raise an IOError
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = IOError("Permission denied")
            with pytest.raises(
                RuntimeError,
                match="Generated Fernet encryption key could not be written to file.",
            ):
                result = encrypt.generate_new_key("/non_writable/secret.key")
                assert result is False
            assert any(record.levelname == "WARNING" for record in caplog.records)
            assert "Could not write key" in caplog.text


def test_read_key_success(app, tmp_path):
    """Test reading an existing key file successfully."""
    key_file = tmp_path / "secret.key"
    expected_key = b"test_key_content"
    key_file.write_bytes(expected_key)

    with app.app_context():
        key = encrypt.read_key(str(key_file))
        assert key == expected_key


def test_read_key_not_found(app):
    """Test that reading a non-existent key file raises a RuntimeError."""
    with app.app_context():
        mock_logger = MagicMock()
        app.logger = mock_logger

        with pytest.raises(RuntimeError, match="Error reading secret key file."):
            encrypt.read_key("/non_existent/secret.key")

        mock_logger.error.assert_called_once()
        assert "Error reading secret key file" in mock_logger.error.call_args[0][0]


@patch("restikls.lib.encrypt.generate_new_key")
@patch("os.path.exists", return_value=False)
def test_init_cipher_generates_new_key(mock_exists, mock_generate, app):
    """Test that init_cipher generates a new key if one doesn't exist."""
    new_key = Fernet.generate_key()
    mock_generate.return_value = new_key

    with app.app_context():
        encrypt.init_cipher()

        mock_exists.assert_called_once()
        mock_generate.assert_called_once()
        assert isinstance(encrypt.cipher, Fernet)


@patch("restikls.lib.encrypt.read_key")
@patch("os.path.exists", return_value=True)
def test_init_cipher_reads_existing_key(mock_exists, mock_read, app):
    """Test that init_cipher reads an existing key."""
    existing_key = Fernet.generate_key()
    mock_read.return_value = existing_key

    with app.app_context():
        encrypt.init_cipher()

        mock_exists.assert_called_once()
        mock_read.assert_called_once()
        assert isinstance(encrypt.cipher, Fernet)


def test_encrypt_decrypt_roundtrip(app, tmp_path):
    """Test that encrypting and then decrypting a key returns the original."""
    key_file = os.path.join(tmp_path, "test_secret.key")
    app.config["KEY_FILE"] = key_file
    # Ensure a key file exists for the test
    if not os.path.exists(key_file):
        encrypt.generate_new_key(key_file)

    original_repo_cred = credentials.ResticCredentials(
        repo_path="/test/repo",
        repo_key="my-super-secret-password",
        timestamp=time.time(),
    )

    with app.app_context():
        # Reset cipher to ensure it's initialized within the context
        encrypt.cipher = None

        encrypted = encrypt.encrypt_repo_cred(original_repo_cred)
        assert isinstance(encrypted, str)

        decrypted = encrypt.decrypt_repo_cred(encrypted)
        assert decrypted.repo_key == original_repo_cred.repo_key


def test_decrypt_failure_logs_error(app, monkeypatch):
    """Test that a decryption failure raises a RuntimeError and logs an error."""
    with app.app_context():
        # Initialize a valid cipher first
        encrypt.init_cipher()

        mock_logger = MagicMock()
        monkeypatch.setattr(app, "logger", mock_logger)

        with pytest.raises(RuntimeError, match="Repo credentials decryption failed."):
            encrypt.decrypt_repo_cred("this-is-not-a-valid-encrypted-string")

        mock_logger.error.assert_called_once()
        assert (
            "Failed to decrypt the repo credentials"
            in mock_logger.error.call_args[0][0]
        )


def test_generate_new_key_general_exception(app, tmp_path, monkeypatch, caplog):
    """Test general exception during key generation raises RuntimeError."""
    caplog.set_level(logging.WARNING)
    key_file = tmp_path / "secret.key"
    mock_generate = MagicMock()

    monkeypatch.setattr(encrypt.Fernet, "generate_key", mock_generate)
    mock_generate.side_effect = Exception("Unexpected error")
    with pytest.raises(RuntimeError, match="Fernet encryption key generation failed."):
        encrypt.generate_new_key(str(key_file))

    assert any(record.levelname == "WARNING" for record in caplog.records)
    assert "Failed to generate fernet encryption key" in caplog.text


@pytest.mark.skipif(sys.platform == "win32", reason="chmod not run on Windows")
def test_generate_new_key_chmod_failure(app, tmp_path, caplog):
    """Test failure in os.chmod during key generation."""
    caplog.set_level(logging.INFO)
    key_file = tmp_path / "secret.key"

    with (
        patch("os.chmod") as mock_chmod,
        app.app_context(),
        pytest.raises(RuntimeError),
    ):
        mock_chmod.side_effect = OSError("Permission error")
        result = encrypt.generate_new_key(str(key_file))
        assert result is False  # Key generated, but chmod failed, so return false
        assert os.path.exists(key_file)
        assert f"Generating new encryption key at '{key_file}'..." in caplog.text
        assert "Permission error" in caplog.text


def test_read_key_general_exception(app, tmp_path, caplog):
    """Test general exception during key reading raises RuntimeError."""
    key_file = tmp_path / "secret.key"
    key_file.write_bytes(b"test_key")
    caplog.set_level(logging.ERROR)

    with patch("builtins.open") as mock_open:
        mock_open.side_effect = Exception("Unexpected error")

        with app.app_context():
            with pytest.raises(RuntimeError, match="Secret key read failed."):
                encrypt.read_key(str(key_file))
        assert "Secret key read failed" in caplog.text


def test_init_cipher_generate_returns_false(app, monkeypatch):
    """Test init_cipher when generate_new_key returns False."""
    mock_generate = MagicMock(return_value=False)
    monkeypatch.setattr(encrypt, "generate_new_key", mock_generate)
    with patch("os.path.exists", return_value=False):
        with pytest.raises(RuntimeError, match="Cipher initialization failed."):
            encrypt.init_cipher()


def test_init_cipher_invalid_key_content(app, tmp_path):
    """Test init_cipher with invalid (malformed) key content."""
    key_file = tmp_path / "secret.key"
    key_file.write_bytes(b"abc")  # Too short for Fernet
    app.config["KEY_FILE"] = str(key_file)

    with patch("os.path.exists", return_value=True):
        with app.app_context():
            with pytest.raises(
                RuntimeError
            ):  # Fernet raises ValueError for invalid key
                encrypt.init_cipher()


def test_init_cipher_fernet_init_exception(app, tmp_path, caplog):
    """Test general exception during Fernet initialization."""
    key_file = tmp_path / "secret.key"
    key_file.write_bytes(Fernet.generate_key())
    caplog.set_level(logging.ERROR)

    with patch("cryptography.fernet.Fernet.__init__") as mock_fernet:
        mock_fernet.side_effect = Exception("Fernet init error")

        with app.app_context():
            with pytest.raises(RuntimeError, match="Cipher initialization failed."):
                encrypt.init_cipher()

        assert any(record.levelname == "ERROR" for record in caplog.records)
        assert "Failed to initialize the cipher" in caplog.text


def test_encrypt_repo_cred_encryption_failure(app, monkeypatch, caplog):
    """Test failure during encryption raises RuntimeError."""
    with app.app_context():
        caplog.set_level(logging.ERROR)
        encrypt.init_cipher()  # Ensure cipher is initialized

        mock_encrypt = MagicMock(side_effect=Exception("Encryption error"))
        monkeypatch.setattr(encrypt.cipher, "encrypt", mock_encrypt)

        with pytest.raises(RuntimeError, match="Repo credentials encryption failed."):
            encrypt.encrypt_repo_cred("test_key")  # type: ignore

        assert any(record.levelname == "ERROR" for record in caplog.records)
        assert "Failed to encrypt the repo credentials" in caplog.text


# Tests for Invalid Data Inputs

def test_encrypt_repo_cred_invalid_type(app):
    """Test encrypting with non-string input raises appropriate error."""
    with app.app_context():
        encrypt.init_cipher()

        with pytest.raises(RuntimeError):  # Since 'encode' called on non-str
            # int instead of str
            encrypt.encrypt_repo_cred(123)  # type: ignore

def test_decrypt_repo_cred_invalid_type(app):
    """Test decrypting with non-string input raises appropriate error."""
    with app.app_context():
        encrypt.init_cipher()

        with pytest.raises(RuntimeError):  # Since 'encode' called on non-str
            # int instead of str
            encrypt.decrypt_repo_cred(123)  # type: ignore


def test_decrypt_repo_cred_invalid_token(app, monkeypatch, caplog):
    """Test decryption with invalid token (specific Fernet error)."""
    with app.app_context():
        encrypt.init_cipher()
        caplog.set_level(logging.ERROR)

        mock_decrypt = MagicMock(side_effect=InvalidToken("Invalid token"))
        monkeypatch.setattr(encrypt.cipher, "decrypt", mock_decrypt)

        with pytest.raises(RuntimeError, match="Repo credentials decryption failed."):
            encrypt.decrypt_repo_cred("invalid_encoded_string")

        assert any(record.levelname == "ERROR" for record in caplog.records)
        assert "Failed to decrypt the repo credentials" in caplog.text
