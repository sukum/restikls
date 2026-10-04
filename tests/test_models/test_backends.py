# File: tests/test_models/test_backends.py
import pytest
from unittest.mock import MagicMock

# Adjust the import based on your project structure if needed
from restikls.models.backends import (
    BackendInput,
    BackendType,
    LocalBackend,
    RESTBackend,
    SFTPBackend,
    determine_backend_type,
    get_repo_scheme,
)

@pytest.fixture
def backend_config(app, tmp_path):
    """
    Fixture to configure necessary application variables for backend validation.
    Leverages the 'app' fixture from conftest.py for the Flask context.
    """
    # Set maximum key length
    app.config["REPO_KEY_MAXLEN"] = 50
    
    # Create a safe base directory for local backend testing
    base_dir = tmp_path / "safe_base_dir"
    base_dir.mkdir(parents=True, exist_ok=True)
    app.config["REPO_BASE_DIR"] = str(base_dir)
    
    # Yield the base_dir path so tests can create subdirectories/files inside it
    yield base_dir

# ---------------------------------------------------------
# BaseBackend / LocalBackend Tests
# ---------------------------------------------------------

def test_base_backend_empty_path(backend_config):
    # Test that empty paths raise a ValueError
    backend = LocalBackend(repo_path="", repo_key="valid_key")
    with pytest.raises(ValueError, match="Repository path cannot be empty"):
        backend.validate()

def test_base_backend_null_byte_path(backend_config):
    # Test protection against null byte injection
    backend = LocalBackend(repo_path="path/with/\0/nullbyte", repo_key="valid_key")
    with pytest.raises(ValueError, match="Null byte detected in repo path"):
        backend.validate()

def test_base_backend_empty_key(backend_config, monkeypatch):
    # Test that empty keys raise a ValueError
    validate_path = MagicMock()
    monkeypatch.setattr(LocalBackend, "validate_path", validate_path)
    backend = LocalBackend(repo_path="valid_path", repo_key="")
    with pytest.raises(ValueError, match="Repository key cannot be empty"):
        backend.validate()

def test_base_backend_key_exceeds_maxlen(backend_config, app, monkeypatch):
    # Test that keys exceeding REPO_KEY_MAXLEN raise a ValueError
    long_key = "a" * (app.config["REPO_KEY_MAXLEN"] + 1)
    validate_path = MagicMock()
    monkeypatch.setattr(LocalBackend, "validate_path", validate_path)
    backend = LocalBackend(repo_path="valid_path", repo_key=long_key)
    with pytest.raises(ValueError, match="Repo key length exceeds allowed maximum length"):
        backend.validate()

def test_local_backend_directory_traversal(backend_config):
    # Test that paths resolving outside REPO_BASE_DIR are blocked
    backend = LocalBackend(repo_path="../../etc/passwd", repo_key="valid_key")
    with pytest.raises(ValueError, match="not within base dir"):
        backend.validate()

def test_local_backend_path_does_not_exist(backend_config):
    # Test that non-existent paths within the base dir are caught
    backend = LocalBackend(repo_path="does_not_exist", repo_key="valid_key")
    with pytest.raises(ValueError, match="does not exist"):
        backend.validate()

def test_local_backend_path_is_not_dir(backend_config):
    # Test that valid paths pointing to a file instead of a directory are caught
    test_file = backend_config / "not_a_dir.txt"
    test_file.touch()
    
    backend = LocalBackend(repo_path="not_a_dir.txt", repo_key="valid_key")
    with pytest.raises(ValueError, match="is not a directory"):
        backend.validate()

def test_local_backend_valid(backend_config):
    # Test a fully valid local backend configuration
    valid_dir = backend_config / "valid_repo"
    valid_dir.mkdir()
    
    backend = LocalBackend(repo_path="valid_repo", repo_key="valid_key")
    # Should not raise any exceptions
    backend.validate()

# ---------------------------------------------------------
# SFTPBackend Tests
# ---------------------------------------------------------

def test_sftp_backend_post_init_sanitization():
    # Test that invisible/invalid characters are stripped from the SSH key
    dirty_key = "\u200b-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\u200b  \n"
    backend = SFTPBackend(repo_path="sftp://host/path", repo_key="key", ssh_key=dirty_key)
    
    assert backend.ssh_key and backend.ssh_key.startswith("-----BEGIN")
    assert backend.ssh_key and "\u200b" not in backend.ssh_key

def test_sftp_backend_invalid_prefix(backend_config):
    # SFTP paths must explicitly start with sftp://
    backend = SFTPBackend(repo_path="http://host/path", repo_key="key", ssh_key="-----BEGIN PRIVATE KEY-----")
    with pytest.raises(ValueError, match="SFTP paths must start with 'sftp://'"):
        backend.validate()

def test_sftp_backend_missing_ssh_key(backend_config):
    # SFTP requires an SSH key
    backend = SFTPBackend(repo_path="sftp://host/path", repo_key="key", ssh_key=None)
    with pytest.raises(ValueError, match="SSH key is required for SFTP repositories"):
        backend.validate()

def test_sftp_backend_invalid_ssh_key_format(backend_config):
    # SFTP requires a PEM-encoded key
    backend = SFTPBackend(repo_path="sftp://host/path", repo_key="key", ssh_key="ssh-rsa AAAAB3NzaC1...")
    with pytest.raises(ValueError, match="Invalid SSH key format"):
        backend.validate()

def test_sftp_backend_valid(backend_config):
    # Test fully valid SFTP backend configuration
    valid_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
    backend = SFTPBackend(repo_path="sftp://host/path", repo_key="key", ssh_key=valid_key)
    # Should not raise any exceptions
    backend.validate()

# ---------------------------------------------------------
# RESTBackend Tests
# ---------------------------------------------------------

def test_rest_backend_invalid_prefix(backend_config):
    # REST paths must explicitly start with rest:http
    backend = RESTBackend(repo_path="http://host/path", repo_key="key")
    with pytest.raises(ValueError, match="RestServer paths must start with 'rest:http'"):
        backend.validate()

def test_rest_backend_valid(backend_config):
    # Test fully valid REST backend configuration
    backend = RESTBackend(repo_path="rest:http://host/path", repo_key="key")
    # Should not raise any exceptions
    backend.validate()


def test_rest_backend_valid_https(backend_config):
    # Test fully valid REST backend configuration
    backend = RESTBackend(repo_path="rest:https://host/path", repo_key="key")
    # Should not raise any exceptions
    backend.validate()

# ---------------------------------------------------------
# Factory Function Tests (get_repo_scheme)
# ---------------------------------------------------------

def test_get_repo_scheme_empty_fallback():
    # Empty paths should fall back to LocalBackend (which will then fail validation)
    backend_input = BackendInput(
        repo_path="",
        repo_key="key",
    )
    backend = get_repo_scheme(backend_input)
    assert isinstance(backend, LocalBackend)

def test_get_repo_scheme_sftp():
    # sftp:// prefix should return SFTPBackend and assign the ssh_key
    backend_input = BackendInput(repo_path="sftp://host/path", repo_key="key", ssh_key="my_key")
    backend = get_repo_scheme(backend_input)
    assert isinstance(backend, SFTPBackend)
    assert backend.ssh_key == "my_key"

def test_get_repo_scheme_rest():
    # rest:http prefix should return RESTBackend
    backend_input = BackendInput(repo_path="rest:http://host/path", repo_key="key")
    backend = get_repo_scheme(backend_input)
    assert isinstance(backend, RESTBackend)

def test_get_repo_scheme_default():
    # Unrecognized prefixes or local paths should default to LocalBackend
    backend_input = BackendInput(repo_path="/var/backups/restic", repo_key="key")
    backend = get_repo_scheme(backend_input)
    assert isinstance(backend, LocalBackend)

def test_get_repo_scheme_empty_fallback_with_ssh_key():
    # Empty paths with ssh_key provided should not raise TypeError
    backend_input = BackendInput(repo_path="", repo_key="key", ssh_key="my_key")
    backend = get_repo_scheme(backend_input)
    assert isinstance(backend, LocalBackend)
    assert not hasattr(backend, "ssh_key")

def test_get_repo_scheme_with_backend_input():
    # Test instantiating backends using typed BackendInput
    sftp_input = BackendInput(repo_path="sftp://host/path", repo_key="key", ssh_key="my_key")
    sftp_backend = get_repo_scheme(sftp_input)
    assert isinstance(sftp_backend, SFTPBackend)
    assert sftp_backend.ssh_key == "my_key"

    rest_input = BackendInput(repo_path="rest:http://host/path", repo_key="key")
    rest_backend = get_repo_scheme(rest_input)
    assert isinstance(rest_backend, RESTBackend)

    local_input = BackendInput(repo_path="/var/backups/restic", repo_key="key")
    local_backend = get_repo_scheme(local_input)
    assert isinstance(local_backend, LocalBackend)

    empty_input = BackendInput(repo_path="", repo_key="key", ssh_key="unused_key")
    fallback_backend = get_repo_scheme(empty_input)
    assert isinstance(fallback_backend, LocalBackend)

def test_determine_backend_type():
    assert determine_backend_type("sftp://user@host/path") == BackendType.SFTP
    assert determine_backend_type("rest:http://host/path") == BackendType.REST
    assert determine_backend_type("rest:https://host/path") == BackendType.REST
    assert determine_backend_type("/var/backups/restic") == BackendType.LOCAL
    assert determine_backend_type("") == BackendType.LOCAL

def test_backend_type_properties():
    local = LocalBackend(repo_path="/path", repo_key="key")
    assert local.backend_type == BackendType.LOCAL

    sftp = SFTPBackend(repo_path="sftp://path", repo_key="key", ssh_key="k")
    assert sftp.backend_type == BackendType.SFTP

    rest = RESTBackend(repo_path="rest:http://path", repo_key="key")
    assert rest.backend_type == BackendType.REST