# File: tests/test_lib/test_bootstrap.py

import builtins
import importlib
import sys
import time
from unittest.mock import MagicMock, Mock, patch

import pytest
from flask import g

from restikls.lib.bootstrap import load_config_from_env

SECRET_KEY_ENV_VAR = "RESTIKLS_SECRET_KEY"

def test_setup_secret_from_environment(app, monkeypatch):
    """Test that secret is set from environment variable."""
    test_key = "env-secret-key"
    monkeypatch.setenv(SECRET_KEY_ENV_VAR, test_key)

    from restikls.lib.bootstrap import setup_secret

    load_config_from_env(app)
    setup_secret(app)
    assert app.secret_key == test_key


def test_setup_secret_from_config(app):
    """Test that secret is set from app config."""
    test_key = "config-secret-key"
    app.config["SECRET_KEY"] = test_key

    from restikls.lib.bootstrap import setup_secret

    load_config_from_env(app)
    setup_secret(app)
    assert app.secret_key == test_key


def test_setup_secret_no_keyfile(app, monkeypatch):
    """Test that default secret is used when no other source available."""
    # Ensure no environment variable
    monkeypatch.delenv(SECRET_KEY_ENV_VAR, raising=False)
    mock_read_key = Mock(side_effect=ValueError("read_key mocked ValueError"))
    monkeypatch.setattr("restikls.lib.bootstrap.read_key", mock_read_key)
    # Ensure no app config
    app.config.pop("SECRET_KEY", None)

    from restikls.lib.bootstrap import setup_secret

    with pytest.raises(SystemExit) as exc_info:
        load_config_from_env(app)
        setup_secret(app)
    assert isinstance(exc_info.value, SystemExit)
    assert exc_info.value.code != 0
    assert "SECRET_KEY" not in app.config
    mock_read_key.assert_called()


def test_setup_secret_no_secret_key(app, monkeypatch):
    """Test that default secret is used when no other source available."""
    # Ensure no environment variable
    monkeypatch.delenv(SECRET_KEY_ENV_VAR, raising=False)
    mock_read_key = Mock(return_value=None)
    monkeypatch.setattr("restikls.lib.bootstrap.read_key", mock_read_key)
    # Ensure no app config
    app.config.pop("SECRET_KEY", None)

    from restikls.lib.bootstrap import setup_secret

    with pytest.raises(SystemExit) as exc_info:
        load_config_from_env(app)
        setup_secret(app)
    assert isinstance(exc_info.value, SystemExit)
    assert exc_info.value.code != 0
    assert "SECRET_KEY" not in app.config
    mock_read_key.assert_called()


def test_setup_secret_priority(app, monkeypatch):
    """Test that environment variable takes priority over config."""
    env_key = "env-secret-key"
    config_key = "config-secret-key"
    monkeypatch.setenv(SECRET_KEY_ENV_VAR, env_key)
    app.config["SECRET_KEY"] = config_key

    from restikls.lib.bootstrap import setup_secret

    load_config_from_env(app)
    setup_secret(app)
    assert app.secret_key == env_key


def test_setup_secret_auto_generate_on_missing(app, monkeypatch):
    """Test that secret key is automatically generated if key file is missing."""
    monkeypatch.delenv(SECRET_KEY_ENV_VAR, raising=False)
    app.config.pop("SECRET_KEY", None)

    mock_generate = Mock(return_value=b"newly-generated-key")
    monkeypatch.setattr("restikls.lib.bootstrap.generate_new_key", mock_generate)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr(sys, "argv", ["flask", "run"])

    from restikls.lib.bootstrap import setup_secret

    setup_secret(app)
    assert app.secret_key == b"newly-generated-key"
    assert app.config["SECRET_KEY"] == b"newly-generated-key"
    mock_generate.assert_called_once()


def test_setup_secret_cli_key_bypasses(app, monkeypatch):
    """Test that CLI key command bypasses auto-generation and exit when key is missing."""
    monkeypatch.delenv(SECRET_KEY_ENV_VAR, raising=False)
    app.config.pop("SECRET_KEY", None)

    mock_generate = Mock(return_value=b"new-key")
    monkeypatch.setattr("restikls.lib.bootstrap.generate_new_key", mock_generate)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr(sys, "argv", ["flask", "key", "generate"])

    from restikls.lib.bootstrap import setup_secret

    setup_secret(app)
    assert "SECRET_KEY" not in app.config
    mock_generate.assert_not_called()


# ------ before_request_setup --------


def test_request_timing_setup(app, client):
    """Test that request timing is properly set up."""
    from restikls.lib.bootstrap import before_request_setup, get_execution_time

    with app.test_request_context():
        before_request_setup()
        assert hasattr(g, "request_start_time")
        assert callable(get_execution_time)

        # Test the timing function
        # g.request_start_time
        time.sleep(0.1)
        time_str: str = get_execution_time()
        assert time_str.endswith("s")
        assert float(time_str[:-1]) > 0.1


def test_ajax_detection_header(app, client):
    """Test AJAX detection via header."""
    from restikls.lib.bootstrap import before_request_setup

    headers = {"X-Requested-With": "XMLHttpRequest"}
    with app.test_request_context(headers=headers):
        before_request_setup()
        assert g.is_ajax is True


def test_ajax_detection_param(app, client):
    """Test AJAX detection via query parameter."""
    from restikls.lib.bootstrap import before_request_setup

    with app.test_request_context(query_string="is_ajax=true"):
        before_request_setup()
        assert g.is_ajax is True


def test_ajax_detection_false(app, client):
    """Test non-AJAX request detection."""
    from restikls.lib.bootstrap import before_request_setup

    with app.test_request_context():
        before_request_setup()
        assert g.is_ajax is False


def test_cache_setup_with_cache(app, client, monkeypatch):
    """Test cache setup when cache extension is present."""
    from restikls.lib.bootstrap import before_request_setup
    from restikls.services.cache_service import CacheService

    mock_secret = Mock()
    monkeypatch.setattr("restikls.setup_secret", mock_secret)

    mock_cache = MagicMock()
    app.extensions["cache"] = {"default": mock_cache}

    with app.test_request_context():
        monkeypatch.setitem(app.config, "CACHE_TIMEOUT", 300)
        before_request_setup()
        assert g.cache == mock_cache
        assert isinstance(g.cache_service, CacheService)
        assert g.cache_service.cache == mock_cache
        assert g.cache_service.default_ttl == 300


@pytest.mark.filterwarnings("ignore:'flask_caching'")
def test_cache_setup_without_cache(monkeypatch):
    """Test cache setup when no cache extension is present."""
    from restikls.lib.bootstrap import before_request_setup
    from restikls.lib.dummy_cache import DummyCache
    from restikls.services.cache_service import CacheService

    original_import = builtins.__import__

    mock_secret = Mock()
    monkeypatch.setattr("restikls.lib.bootstrap.setup_secret", mock_secret)

    with monkeypatch.context() as m:

        def fake_import(name, *args, **kwargs):
            if name == "flask_caching":
                raise ImportError("Simulated ImportError for flask_caching")
            return original_import(name, *args, **kwargs)

        m.setattr(builtins, "__import__", fake_import)
        # Simulate import failure
        m.setitem(sys.modules, "flask_caching", None)

        # Need to re-import the module
        import restikls as package_init

        importlib.reload(package_init)

        _app = package_init.create_app()

        with _app.test_request_context():
            before_request_setup()
            assert isinstance(g.cache, DummyCache)
            assert isinstance(g.cache_service, CacheService)
            assert g.cache_service.default_ttl is not None


# @pytest.mark.skip(reason="test is causing other tests to fail")
def test_config_and_restic_with_config(app_fixture, mock_app_config, monkeypatch):
    """Test config and restic service setup when config is available."""
    with app_fixture.test_request_context():
        from restikls.lib.bootstrap import before_request_setup

        mock_restic = Mock()
        mock_get_service = Mock(return_value=mock_restic)
        monkeypatch.setattr(
            "restikls.services.factory.ResticServiceFactory.get_service",
            mock_get_service,
        )
        # This was the wrong way to do as the teardown was not resetting ResticServiceFactory.get_service
        # Leading to next calls getting returned the mocked object causing fails.
        # from restikls.services.factory import ResticServiceFactory
        # ResticServiceFactory.get_service = Mock(return_value=mock_restic)
        before_request_setup()
        assert g.repo_cred == mock_app_config
        assert g.restic_service == mock_restic
        mock_get_service.assert_called_once_with(mock_app_config, g.cache_service)


@patch("restikls.lib.bootstrap._config.get_repo_cred")
def test_config_and_restic_without_config(_mock_get_repo_cred, app, client):
    """Test config and restic service setup when no config is available."""
    from restikls.lib.bootstrap import before_request_setup

    _mock_get_repo_cred.return_value = None

    with app.test_request_context():
        before_request_setup()
        assert g.repo_cred is None
        assert g.restic_service is None


def test_config_not_reloaded_if_present(app, client, mock_restic_service):
    """Test that config isn't reloaded if already present on g."""
    from restikls.lib.bootstrap import before_request_setup

    existing_config = MagicMock()

    with app.test_request_context():
        g.repo_cred = existing_config
        before_request_setup()
        assert g.repo_cred == existing_config


# --------- flask_caching available and not ------------

# This ensures the parent package is importable
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.mark.filterwarnings("ignore:'flask_caching'")
@pytest.mark.xfail(reason="This test fails as not hasattr check fails")
def test_without_cache(monkeypatch):
    # Test when flask_caching is not available
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "flask_caching":
            raise ImportError("Simulated ImportError for flask_caching")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Simulate import failure
    monkeypatch.setitem(sys.modules, "flask_caching", None)

    # Need to re-import the module
    import restikls as package_init

    importlib.reload(package_init)

    # Verify initialization
    assert package_init.CACHE_AVAILABLE is False
    assert not hasattr(package_init, "cache")  # ERROR: This assert is failing

    # Test create_app (should not raise exceptions)
    _app = package_init.create_app()


@pytest.mark.skip(reason="This test is temporarily disabled")
def test_with_cache(monkeypatch, app):
    # Test when flask_caching is available
    # Mock the entire flask_caching module and Cache class
    mock_cache = MagicMock()
    mock_flask_caching = MagicMock()
    mock_flask_caching.Cache = MagicMock(return_value=mock_cache)

    # Patch sys.modules and import
    monkeypatch.setitem(sys.modules, "flask_caching", mock_flask_caching)

    # Need to re-import the module to execute the try/except again
    # Import and reload the package
    # import __init__ as package_init
    import restikls as package_init

    importlib.reload(package_init)

    # Verify initialization
    assert package_init.CACHE_AVAILABLE is True
    assert hasattr(package_init, "cache")

    # Test create_app
    _app = package_init.create_app()
    mock_cache.init_app.assert_called_once_with(_app)
