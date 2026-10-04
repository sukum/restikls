# File: tests/test_models/test_credentials.py
from unittest.mock import patch
import pytest
from flask import Flask

# Adjust the import based on your project structure
from restikls.models.credentials import ResticCredentials


@pytest.fixture
def app_context():
    """
    Creates a dummy Flask application and pushes its context.
    This is required because ResticCredentials relies on current_app.
    """
    app = Flask(__name__)
    
    # Set default test configurations
    app.config["SESSION_LIFE"] = 3600  # 1 hour
    app.config["ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY"] = 7200  # 2 hours
    app.debug = True  # Enable debug mode to trigger debug logging branches
    
    with app.app_context():
        yield app


@pytest.fixture
def credentials(app_context):
    """
    Provides a fresh instance of ResticCredentials for each test.
    The timestamp is fixed to a known value (1000.0) for predictable testing.
    """
    return ResticCredentials(
        repo_path="/backup/data",
        repo_key="secret123",
        timestamp=1000.0,
        ssh_key=None
    )


def test_is_expired_false(app_context, credentials, caplog):
    """
    Test that credentials are NOT expired if the current time is within SESSION_LIFE.
    """
    # Mock current time to be exactly 1800 seconds (30 mins) after the timestamp
    with patch("time.time", return_value=2800.0):
        assert credentials.is_expired is False
        
    # Verify the debug logger outputs the remaining validity correctly
    assert "cred valid for 1800.0 more seconds" in caplog.text


def test_is_expired_true(app_context, credentials, caplog):
    """
    Test that credentials ARE expired if the current time exceeds SESSION_LIFE.
    """
    # Mock current time to be 4000 seconds after the timestamp (exceeds 3600)
    with patch("time.time", return_value=5000.0):
        assert credentials.is_expired is True
        
    # Verify the expiration is logged
    assert "Configuration expired" in caplog.text


def test_is_expired_fallback_to_encrypted_validity_zero_session(app_context, credentials):
    """
    Test the edge case where SESSION_LIFE is 0. 
    It should fall back to ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY (7200).
    """
    app_context.config["SESSION_LIFE"] = 0
    
    # 5000 seconds passed. Should not be expired because 5000 < 7200.
    with patch("time.time", return_value=6000.0):
        assert credentials.is_expired is False

    # 8000 seconds passed. Should be expired because 8000 > 7200.
    with patch("time.time", return_value=9000.0):
        assert credentials.is_expired is True


def test_is_expired_fallback_to_encrypted_validity_none_session(app_context, credentials):
    """
    Test the edge case where SESSION_LIFE is None or missing. 
    It should fall back to ENCRYPTED_REPO_CREDENTIALS_OBJ_VALIDITY (7200).
    """
    app_context.config["SESSION_LIFE"] = None
    
    with patch("time.time", return_value=6000.0):
        assert credentials.is_expired is False


def test_contains_magic_method(credentials):
    """
    Validate that the __contains__ method correctly identifies attributes
    within the dataclass dictionary.
    """
    assert "repo_path" in credentials
    assert "repo_key" in credentials
    assert "timestamp" in credentials
    assert "ssh_key" in credentials
    
    # Edge case: Ensure non-existent keys return False cleanly
    assert "non_existent_key" not in credentials


def test_missing_timestamp_edge_case(app_context):
    """
    Test the fallback edge case where the timestamp attribute is somehow missing 
    (handled by getattr default to 0 in the original code).
    """
    # Create credentials but explicitly delete the timestamp attribute
    cred = ResticCredentials(
        repo_path="/backup",
        repo_key="secret",
        timestamp=0.0
    )
    del cred.timestamp
    
    # If timestamp defaults to 0, and current time is 4000, 
    # it exceeds the 3600 SESSION_LIFE.
    with patch("time.time", return_value=4000.0):
        assert cred.is_expired is True