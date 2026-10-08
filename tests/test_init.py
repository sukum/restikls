# File: tests/test_init.py

import importlib
import sys
from unittest.mock import Mock

import pytest
from flask import Flask

# Import the application factory and the module itself to allow for reloading


@pytest.mark.filterwarnings("ignore:Flask-Caching")
def test_app_fixture(app):
    """
    Tests the `app` fixture from conftest.py to ensure it creates a valid app.
    It implicitly tests that create_app can load the 'test_config.toml'.
    """
    assert app is not None
    assert isinstance(app, Flask)
    # These values come from 'tests/test_config.toml'
    assert app.config["TESTING"] is True
    assert app.config["APP_NAME"] == "My Test App"
    assert app.config["SECRET_KEY"] == "a-secret-key-for-testing"


@pytest.mark.filterwarnings("ignore:Flask-Caching")
def test_create_app_with_custom_config(tmp_path):
    """
    Tests that `create_app` can load a specific configuration file.
    """
    # 1. Create a temporary config file for this test
    config_content = """
    TESTING = true
    SECRET_KEY = "a-different-secret-key"
    CUSTOM_VALUE = "hello from test"
    """
    config_file = tmp_path / "custom_config.toml"
    config_file.write_text(config_content)

    # 2. Create the app using the temporary config
    from restikls import create_app

    app = create_app(config_filename=str(config_file))

    # 3. Assert that the configuration was loaded correctly
    assert isinstance(app, Flask)
    assert app.config["TESTING"] is True
    assert app.config["SECRET_KEY"] == "a-different-secret-key"
    assert app.config["CUSTOM_VALUE"] == "hello from test"


@pytest.mark.filterwarnings("ignore:Flask-Caching")
def test_create_app_without_config_file(caplog, monkeypatch):
    """
    Tests that `create_app` handles a missing configuration file gracefully.
    """
    # 1. Call create_app with a path that is guaranteed not to exist
    non_existent_config = "/path/to/a/non/existent/config.toml"
    from restikls import PROJECT_ROOT, create_app

    expected_config_path = PROJECT_ROOT / non_existent_config

    mock_secret = Mock()
    monkeypatch.setattr("restikls.setup_secret", mock_secret)

    app = create_app(config_filename=non_existent_config)

    # 2. Assert that a warning was logged
    assert isinstance(app, Flask)
    assert f"Configuration file '{expected_config_path!s}' not found" in caplog.text
    assert any(record.levelname == "WARNING" for record in caplog.records)


@pytest.mark.filterwarnings("ignore:Flask-Caching")
# @patch('app.__init__.setup_logging')
# @patch('app.__init__.setup_secret')
# @patch('app.__init__.register_filters')
# @patch('app.__init__.register_blueprints')
# @patch('app.__init__.register_hooks_processors')
# def test_all_setup_functions_are_called(
#     mock_hooks, mock_blueprints, mock_filters, mock_secret, mock_logging
# ):
def test_all_setup_functions_are_called(monkeypatch):
    """
    Tests that all the necessary setup and registration functions are called
    during application creation. This test uses the 'app' fixture, which calls
    create_app internally. The mocks intercept the calls made during that process.
    """
    mock_logging = Mock()
    mock_secret = Mock()
    mock_filters = Mock()
    mock_blueprints = Mock()
    mock_hooks = Mock()

    monkeypatch.setattr("restikls.setup_logging", mock_logging)
    monkeypatch.setattr("restikls.setup_secret", mock_secret)
    monkeypatch.setattr("restikls.register_filters", mock_filters)
    monkeypatch.setattr("restikls.register_blueprints", mock_blueprints)
    monkeypatch.setattr("restikls.register_hooks_processors", mock_hooks)

    # The app fixture has already run create_app(), so we just check the mocks.
    from restikls import create_app

    create_app("test_config.toml")

    mock_logging.assert_called_once()
    mock_secret.assert_called_once()
    mock_filters.assert_called_once()
    mock_blueprints.assert_called_once()
    mock_hooks.assert_called_once()

    # Verify that the app instance was passed to each function
    assert isinstance(mock_logging.call_args[0][0], Flask)
    assert isinstance(mock_secret.call_args[0][0], Flask)
    assert isinstance(mock_filters.call_args[0][0], Flask)
    assert isinstance(mock_blueprints.call_args[0][0], Flask)
    assert isinstance(mock_hooks.call_args[0][0], Flask)


# @pytest.mark.skipif(not app_init_module.CACHE_AVAILABLE, reason="flask_caching is not installed")
# @pytest.mark.skip(reason="AttributeError: 'method-wrapper' object has no attribute 'CACHE_AVAILABLE'")
def test_cache_initialization_when_available(app):
    """
    Tests that the cache extension is initialized if flask_caching is installed.
    This test only runs if the library is present.
    """
    # The 'app' fixture from conftest.py creates the app instance
    assert "cache" in app.extensions
    from restikls import cache

    assert cache in app.extensions.get("cache")
    backend_cache = app.extensions.get("cache").get(cache)
    assert "NullCache" in str(type(backend_cache))


# @pytest.mark.filterwarnings("ignore:'flask_caching'")
def test_cache_initialization_when_unavailable(monkeypatch, caplog, recwarn, tmp_path):
    """
    Tests the app's behavior when 'flask_caching' is not installed.
    It simulates an ImportError and verifies the appropriate warnings are logged.
    """
    import logging

    caplog.set_level(logging.INFO)  # Set the caplog level to INFO and above

    # 1. Simulate the ImportError by hiding the 'flask_caching' module
    monkeypatch.setitem(sys.modules, "flask_caching", None)

    # 2. Reload the app's __init__ module to re-run the try/except block
    # This is crucial for the test to work as intended.
    # from restikls import __init__ as app_init_module
    import restikls as app_init_module

    importlib.reload(app_init_module)
    assert not app_init_module.CACHE_AVAILABLE

    # 3. Create a minimal config to allow app creation
    config_file = tmp_path / "config.toml"
    config_file.write_text("SECRET_KEY = 'temp'")

    # 4. Create the app using the reloaded module's factory
    # from restikls import create_app
    app = app_init_module.create_app(config_filename=str(config_file))

    # 5. Assert that the correct log messages were emitted and cache is not setup
    assert "'flask_caching' library not installed" in caplog.text
    # Verify both the INFO log and the developer WARNING were issued
    assert any(
        r.levelname == "INFO" and "'flask_caching' library not installed" in r.message
        for r in caplog.records
    )
    # assert any(r.levelname == 'WARNING' and "'flask_caching' library not installed" in r.message for r in caplog.records)
    # captured = capsys.readouterr()
    # assert("'flask_caching' library not installed" in captured.out)
    assert len(recwarn) == 1
    assert "'flask_caching' library not installed" in str(recwarn.pop().message)

    assert "cache" not in app.extensions

    # 6. Clean up: Restore the original module state to avoid side effects
    monkeypatch.undo()
    importlib.reload(app_init_module)
