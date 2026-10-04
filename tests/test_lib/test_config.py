# File: tests/test_lib/test_config.py

import os
import time
from unittest.mock import MagicMock, Mock, call

import pytest
from flask import Response, make_response

import restikls.lib.encrypt as encrypt
from restikls.lib.encrypt import init_cipher

# import restikls.config as config_obj

# Note: We import the module to be tested inside each test function
# to ensure mocks are applied correctly before the module's code is executed.


def test_init_cipher_creates_key(tmp_path, app, monkeypatch):
    """
    Test that init_cipher creates a new key file if one doesn't exist.
    """
    key_file = os.path.join(tmp_path, "test_secret.key")
    app.config["KEY_FILE"] = key_file
    # print(app.config.get('KEY_FILE'))

    # Reset the global cipher to ensure it's re-initialized
    monkeypatch.setattr(encrypt, "cipher", None)

    with app.app_context():
        init_cipher()
        assert os.path.exists(key_file)
        with open(key_file, "rb") as f:
            key = f.read()
            assert len(key) > 30  # Fernet keys are base64 encoded


@pytest.mark.exclude_autouse
def test_config_set_get_clear(tmp_path, app, monkeypatch):
    """
    Test the full lifecycle: setting, getting, and clearing config via config functions.
    """
    from restikls.lib.config import clear_config, get_repo_cred, set_config

    with app.app_context():
        # Use a temporary key file to ensure isolation and test real encryption
        key_file = os.path.join(tmp_path, "test_secret.key")
        app.config["KEY_FILE"] = key_file
        monkeypatch.setattr(encrypt, "cipher", None)

        repo_path = "/test/repo"
        repo_key = "test_password"
        ssh_key = "ssh key"
        # 1. Set the configuration
        with app.test_request_context():
            response = make_response("Setting config")
            set_config(response, repo_path, repo_key, ssh_key)
            # Extract cookies to simulate a new request
            cookies_out = {
                h.split("=", 1)[0]: h.split(";")[0].split("=", 1)[1]
                for h in response.headers.getlist("Set-Cookie")
            }
        # 2. Simulate a new request with these cookies to test get_repo_cred
        with app.test_request_context(
            environ_base={
                "HTTP_COOKIE": "; ".join([f"{k}={v}" for k, v in cookies_out.items()])
            }
        ):
            repo_cred = get_repo_cred()
            assert repo_cred is not None
            assert repo_cred.repo_path == repo_path
            assert repo_cred.repo_key == repo_key

        # 3. Clear the configuration
        with app.test_request_context():
            clear_response = make_response("Clearing config")
            clear_config(clear_response)
            clear_cookies_header = clear_response.headers.getlist("Set-Cookie")
            assert any(
                "repo_cred=;" in h and "Max-Age=0" in h for h in clear_cookies_header
            )


def test_build_environment_config(app, monkeypatch):
    """
    Tests that the environment dictionary is built correctly.
    """
    from restikls.lib import config as config_module

    # 1. Arrange
    # Mock os.environ to have a predictable state
    mock_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "USERPROFILE": "C:\\Users\\Test",
        "SystemRoot": "C:\\Windows",
        "UNRELATED_VAR": "ignore_this",
    }
    monkeypatch.setattr(config_module.os, "environ", mock_env)

    repo_path = "/my/repo"
    repo_key = "secret_password"

    with app.test_request_context():
        # 2. Act
        result_env = config_module.build_environment_config(repo_path, repo_key)

    # 3. Assert
    # Check that restic variables are set
    assert result_env["RESTIC_REPOSITORY"] == repo_path
    assert result_env["RESTIC_PASSWORD"] == repo_key

    # Check that required OS variables were included
    assert result_env["PATH"] == "/usr/bin:/bin"
    assert result_env["HOME"] == "/home/user"
    assert result_env["USERPROFILE"] == "C:\\Users\\Test"

    # Check that unrelated variables were excluded
    assert "UNRELATED_VAR" not in result_env


@pytest.mark.exclude_autouse
def test_get_repo_cred_success_with_ssh(app, monkeypatch):
    """
    Tests get_repo_cred successfully retrieves and builds config with an SSH key.
    """
    from restikls.lib import config as config_module
    from restikls.models.credentials import ResticCredentials

    # 1. Arrange
    # Mock dependencies
    _config_dict = {
        "repo_path": "/test/repo",
        "repo_key": "decrypted_repo_key",
        "timestamp": time.time(),
        "ssh_key": "decrypted_ssh_key",
    }
    mock_decrypt = Mock(return_value=ResticCredentials(**_config_dict)) # type: ignore[missing-argument]
    monkeypatch.setattr(config_module, "decrypt_repo_cred", mock_decrypt)

    # mock_build_env = Mock(return_value={"ENV_VAR": "value"})
    # monkeypatch.setattr(config_module, "build_environment_config", mock_build_env)

    # Simulate a request with cookies
    with app.test_request_context(
        environ_base={"HTTP_COOKIE": "repo_cred=encrypted_repo"}
    ):
        # 2. Act
        repo_cred = config_module.get_repo_cred()

    # 3. Assert
    assert repo_cred is not None
    assert repo_cred.repo_path == _config_dict["repo_path"]
    assert repo_cred.repo_key == _config_dict["repo_key"]
    assert repo_cred.ssh_key == _config_dict["ssh_key"]
    # assert config["run_options"]["env"] == {"ENV_VAR": "value"}
    # mock_build_env.assert_called_once_with(
    #     _config_dict["repo_path"], _config_dict["repo_key"]
    # )
    assert mock_decrypt.call_count == 1


@pytest.mark.exclude_autouse
def test_get_repo_cred_missing_cookies(app):
    """
    Tests that get_repo_cred returns None if essential cookies are missing.
    """
    from restikls.lib import config as config_module

    # 1. Arrange: Simulate a request with only one of the required cookies
    with app.test_request_context(environ_base={"HTTP_COOKIE": "repo_path=/test/repo"}):
        # 2. Act
        config = config_module.get_repo_cred()
        # 3. Assert
        assert config is None


@pytest.mark.exclude_autouse
def test_get_repo_cred_decryption_failure(app, monkeypatch, caplog):
    """
    Tests that get_repo_cred returns None and logs an error if decryption fails.
    """
    # 1. Arrange
    # Mock decryption to raise an error
    monkeypatch.setattr(
        "restikls.lib.config.decrypt_repo_cred",
        Mock(side_effect=Exception("Decryption failed")),
    )
    # monkeypatch.setattr(
    #     "restikls.lib.config.decrypt_repo_cred",
    #     lambda *args, **kwargs: ValueError("Decryption failed!")
    # )

    from restikls.lib.config import get_repo_cred

    with app.test_request_context(environ_base={"HTTP_COOKIE": "repo_cred=bad_key"}):
        # 2. Act
        config = get_repo_cred()

    # 3. Assert
    assert config is None
    assert "Failed to decrypt" in caplog.text
    assert "Decryption failed" in caplog.text


# @pytest.mark.skip
# @pytest.mark.parametrize(
#     "cookies, expected",
#     [
#         ("repo_cred=some_key", True),
#         ("repo_path=/p", False),
#         ("", False),
#     ],
# )
# def test_has_ssh_key(app, cookies, expected):
#     """
#     Tests the has_ssh_key helper function.
#     """
#     from restikls.lib import config as config_module

#     with app.test_request_context(environ_base={"HTTP_COOKIE": cookies}):
#         assert config_module.has_ssh_key() is expected


def test_set_config_sets_all_cookies(app, monkeypatch):
    """
    Tests that set_config correctly encrypts data and sets all cookies
    when all values are provided.
    """
    from restikls.lib import config as config_module

    # 1. Arrange
    # Mock the encryption function with enough return values for this scenario
    mock_encrypt = Mock(
        side_effect=[
            "encrypted_repo_cred",
        ]
    )
    monkeypatch.setattr(config_module, "encrypt_repo_cred", mock_encrypt)

    # Create a real Response object to modify
    response = Response("test response")

    with app.test_request_context():
        # 2. Act
        config_module.set_config(response, "/my/repo", "repo_pass", "ssh_content")

    # 3. Assert
    cookies = response.headers.getlist("Set-Cookie")
    assert any("repo_cred=encrypted_repo_cred" in c for c in cookies)
    # Ensure delete_cookie was not called (No longer relevant)
    # assert not any("Expires=Thu, 01-Jan-1970" in c for c in cookies)


"""
Skipping as earlier code used to set and clear ssh_key cookie,
which has been replaced by repo_cred now
"""


@pytest.mark.skip
def test_set_config_clears_cookies(app, monkeypatch):
    """
    Tests that set_config correctly deletes cookies when corresponding
    values are empty or False.
    """
    from restikls.lib import config as config_module

    # 1. Arrange
    # Only the repo_key will be encrypted in this scenario.
    mock_encrypt = Mock(side_effect=["encrypted_repo_cred"])
    monkeypatch.setattr(config_module, "encrypt_repo_cred", mock_encrypt)

    response = Response("test response")

    with app.test_request_context():
        # 2. Act
        # ssh_key is an empty string
        config_module.set_config(response, "/my/repo", "repo_pass", ssh_key="")

    # 3. Assert
    cookies = response.headers.getlist("Set-Cookie")

    # Check that cookies were set
    assert any("repo_cred=encrypted_repo_cred" in c for c in cookies)

    # Check that specific cookies were deleted
    # A deletion is a cookie set with an expiration date in the past.
    # print(cookies)
    assert any("repo_cred=;" in c and "Expires=Thu, 01 Jan 1970" in c for c in cookies)

    # Make sure we only tried to encrypt the repo_key
    mock_encrypt.assert_has_calls([call("/my/repo"), call("repo_pass")], any_order=True)


def test_clear_config(app):
    """
    Tests that clear_config deletes all relevant cookies.
    """
    from restikls.lib import config as config_module

    # 1. Arrange
    # Use a mock response to easily verify calls
    mock_response = MagicMock(spec=Response)

    with app.test_request_context():
        # 2. Act
        config_module.clear_config(mock_response)

    # 3. Assert
    mock_response.delete_cookie.assert_any_call("repo_cred")
    assert mock_response.delete_cookie.call_count == 1
