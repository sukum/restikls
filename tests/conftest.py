# File: tests/conftest.py

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the application factory from your refactored app.py
# If you haven't refactored to an app factory, you would import the 'app' object directly.
# from restikls import app as flask_app
from restikls import create_app  # Import create_app from the app package

if __name__ == "__main__":
    # Assuming create_app function is defined in app/__init__.py
    current_app = create_app()
    # You can specify host, port, debug mode here
    # For development, you often run with FLASK_APP and flask run
    # but this is useful for direct execution or Gunicorn/Waitress setup
    current_app.run(debug=True)


@pytest.fixture(scope="function")
def app():
    """
    Creates and configures a new app instance for each test session.
    Using a temporary file for the config ensures tests are isolated.
    """
    # Get the path to the test config file
    config_path = os.path.join(os.path.dirname(__file__), "test_config.toml")

    # Use the application factory to create the app
    app = create_app(config_filename=config_path)

    # Clear any existing handlers
    app.logger.handlers = []
    # Set level to DEBUG to ensure all messages get through
    app.logger.setLevel("DEBUG")

    # Establish an application context before running the tests
    with app.app_context():
        # You could initialize a test database here if you had one
        pass
        yield app


@pytest.fixture(scope="function")
def app_fixture():
    """
    Creates and configures a new app instance for each test session.
    Using a temporary file for the config ensures tests are isolated.
    """
    # Get the path to the test config file
    config_path = os.path.join(os.path.dirname(__file__), "test_config.toml")

    # Use the application factory to create the app
    app = create_app(config_filename=config_path)

    # Establish an application context before running the tests
    with app.app_context():
        # You could initialize a test database here if you had one
        pass
        yield app


@pytest.fixture
def client(app):
    """A test client for the app."""
    with app.test_client() as client:
        # Save the original before_request
        # original_before_request = client.application.before_request_funcs.get(None, [])
        # Clear or replace before_request
        # client.application.before_request_funcs[None] = []  # Disable all

        # # Initialize your service here
        # from flask import g
        # g.restic_service = MagicMock()
        # g.request_time = lambda: '1'
        # g.is_ajax = False

        yield client

        # client.application.before_request_funcs[None] = original_before_request


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture(autouse=True)
def mock_app_config(request, monkeypatch):
    """
    Fixture to mock the application's configuration for all tests.

    This fixture is set to autouse=True, so it will be automatically
    applied to every test function without needing to be explicitly
    requested as an argument.

    It patches the `get_config` function to return a predefined
    dictionary, ensuring a consistent configuration state for testing.
    """
    # Check if the test has the exclude_autouse marker
    if request.node.get_closest_marker("exclude_autouse"):
        yield None  # Explicitly yield None when skipping
        return  # Skip fixture for marked tests

    # 1. Define the mock configuration data
    from restikls.models.credentials import ResticCredentials
    repo_cred = ResticCredentials(
        repo_path="/repo",
        repo_key="password",
        ssh_key="ssh key",
        timestamp=time.time(),
    )

    # mock_config = {
    #     "repo_cred": repo_cred,
    #     "PAGE_RECORDS": 20,
    #     "run_options": {},
    # }
    mock_config = repo_cred

    # 2. Use monkeypatch to replace the real get_config function
    #    with a Mock object that returns our mock_config dictionary.
    #
    #    The string 'app.routes.config_routes.get_config' is the
    #    full import path to the object you want to patch.
    monkeypatch.setattr(
        "restikls.lib.config.get_repo_cred", Mock(return_value=mock_config)
    )

    # Note: No 'yield' or 'return' is needed here. The monkeypatch fixture
    # automatically handles the teardown (restoring the original function)
    # after the test completes.
    yield mock_config


@pytest.fixture
def local_config():
    """Fixture for a sample config dictionary."""
    from restikls.models.credentials import ResticCredentials
    repo_cred = ResticCredentials(
        repo_path="/test/repo",
        repo_key="test_password",
        timestamp=time.time(),
    )
    return repo_cred


@pytest.fixture
def sftp_config():
    """Fixture for a sample SFTP repository config."""
    from restikls.models.credentials import ResticCredentials
    repo_cred = ResticCredentials(
        repo_path="sftp://user@host//test/repo",
        repo_key="test_password",
        ssh_key="---BEGIN SSH PRIVATE KEY---",
        timestamp=time.time(),
    )
    return repo_cred

@pytest.fixture
def rest_config():
    """Fixture for a sample REST repository config."""
    from restikls.models.credentials import ResticCredentials
    repo_cred = ResticCredentials(
        repo_path="rest:http://user:pass@host//test/repo",
        repo_key="test_password",
        timestamp=time.time(),
    )
    return repo_cred


@pytest.fixture
def cache_service():
    """Fixture for a mock cache service."""
    mock = MagicMock()
    mock.has.return_value = False  # Default to cache miss
    return mock


@pytest.fixture
def restic_service_local(app, local_config, cache_service):
    """Fixture for ResticService instance."""
    # return LocalResticService(cache_service, local_config)
    from restikls.services.factory import ResticServiceFactory

    return ResticServiceFactory.get_service(local_config, cache_service)


@pytest.fixture
def restic_service_sftp(app, sftp_config, cache_service):
    """Fixture for ResticService instance."""
    # return SftpResticService(cache_service, sftp_config)
    from restikls.services.factory import ResticServiceFactory

    return ResticServiceFactory.get_service(sftp_config, cache_service)


@pytest.fixture
def mock_restic_service(app, monkeypatch):
    mock_service = MagicMock()
    monkeypatch.setattr(
        "restikls.services.factory.ResticServiceFactory.get_service",
        lambda *args, **kwargs: mock_service,
    )
    monkeypatch.setattr(
        "restikls.lib.bootstrap.ResticServiceFactory.get_service",
        lambda *args, **kwargs: mock_service,
    )
    return mock_service
