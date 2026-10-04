# File: src/restikls/lib/bootstrap.py
"""
Bootstrap module for initializing Flask app components, blueprints, hooks, and secrets.
"""

import hashlib
import os
import sys
import time
from dataclasses import is_dataclass
from typing import Callable

from flask import Flask, current_app, g, request

from ..cli import key as key_cli  # Renamed due to key route conflict

# Renamed as 'file_routes' to avoid conflict with 'file' keyword
from ..models.credentials import ResticCredentials
from ..routes import config_routes, dashboard, key, manage, snapshot
from ..routes import file as file_routes
from ..services.cache_service import CacheService

# Import the factory, not the service class directly
from ..services.factory import ResticServiceFactory

# from .config import get_config
from . import config as _config
from .dummy_cache import DummyCache
from .encrypt import generate_new_key, read_key


def load_template_globals() -> dict[str, str | bool | Callable]:
    """
    Injects global variables into the Jinja2 template context.
    Returns:
        dict: A dictionary of variables to be made available in all templates.
    """
    is_xmlhttprequest: bool = (
        str(request.headers.get("X-Requested-With")).lower() == "xmlhttprequest"
    )

    return {
        "is_xmlhttprequest": is_xmlhttprequest,
        "get_execution_time": get_execution_time,
    }


def get_execution_time() -> str:
    """
    Returns the execution time of the current request.
    This is used in templates to display how long the request took.
    """
    if hasattr(g, "request_start_time"):
        return "%.5fs" % (time.time() - g.request_start_time)
    return "0.00000s"


def before_request_setup() -> None:
    """
    Actions to perform before each request.
    - Sets up request timing for performance monitoring.
    - Attaches cache and restic service objects to the request global `g`.
    - Determines if the request is an AJAX request.
    """
    # Ignore for static files
    if request.endpoint == "static":
        return

    g.request_start_time = time.time()

    # Determine if the request is an AJAX request for consistent handling in routes/templates.
    # We check the standard header first, then fall back to a query parameter.
    g.is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or bool(
        request.args.get("is_ajax", "")
    )

    # Get repo_cred if not already present on `g`
    if not hasattr(g, "repo_cred") or not g.repo_cred:
        g.repo_cred = _config.get_repo_cred()

    # Use the factory to create the correct restic service instance
    if g.repo_cred:
        # Attach the first configured cache to the request global `g`
        if "cache" in current_app.extensions:
            g.cache = next(iter(current_app.extensions["cache"].values()))
            ttl = current_app.config.get("CACHE_TIMEOUT", None)
            assert isinstance(g.repo_cred, ResticCredentials)
            key_prefix_seed = g.repo_cred.repo_path
            # 10 char hex string
            key_prefix = hashlib.blake2b(key_prefix_seed.encode(), digest_size=5).hexdigest()
            g.cache_service = CacheService(
                g.cache, ttl, key_prefix, debug=current_app.config.get("DEBUG", False)
            )
        else:
            g.cache = DummyCache()
            g.cache_service = CacheService(g.cache)
        g.restic_service = ResticServiceFactory.get_service(g.repo_cred, g.cache_service)
    else:
        # No config means we can't have a functional restic service.
        # The @cred_required decorator will handle redirection.
        g.restic_service = None


def register_blueprints(app: Flask) -> None:
    """Register all Flask blueprints with the app."""
    # Grouping blueprint registrations makes it easy to see all routes.
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(snapshot.bp)
    app.register_blueprint(file_routes.bp)
    app.register_blueprint(key.bp)
    app.register_blueprint(config_routes.bp)
    app.register_blueprint(manage.bp)
    # Register CLI command blueprint
    app.register_blueprint(key_cli.bp)


def register_hooks_processors(app: Flask) -> None:
    """Register request hooks and template context processors."""
    # Register a function to run before each request.
    app.before_request(before_request_setup)
    # Register a context processor to inject variables into templates.
    app.context_processor(load_template_globals)


def load_config_from_env(app: Flask) -> None:
    """
    Overrides configuration from config.toml with environment variables.
    """
    app.logger.info("Checking for environment variable configuration overrides.")
    app.config.from_prefixed_env('RESTIKLS')


def is_cli_key_command() -> bool:
    """Check if invoked via CLI for key management or help."""
    return any(arg in sys.argv for arg in ("key", "--help", "-h"))


def setup_secret(app: Flask) -> None:
    """Set up Flask secret key from environment or config."""
    # 2. Setup secret key from environment if available
    # or use hardcoded one if not loaded from config file
    # Get secret key from environment or generate a persistent one
    if "SECRET_KEY" in app.config and app.config["SECRET_KEY"]:
        app.secret_key = app.config["SECRET_KEY"]
        return

    # import secrets
    # app.secret_key = secrets.token_hex(32)
    key_file_path = app.config.get("KEY_FILE")
    try:
        if key_file_path:
            if not os.path.exists(key_file_path):
                # Allow CLI key management commands to handle generation themselves
                if is_cli_key_command():
                    return
                app.logger.info(
                    f"Secret key file not found. Generating new key at '{key_file_path}'..."
                )
                encryption_key = generate_new_key(key_file_path)
            else:
                encryption_key = read_key(key_file_path)

            if encryption_key:
                app.secret_key = encryption_key
                app.config["SECRET_KEY"] = encryption_key
                return
    except Exception as e:
        msg = f"Error reading secret key. {e}"
        app.logger.error(msg)
        print(msg, file=sys.stderr)
        sys.exit(1)

    if not (
        "SECRET_KEY" in app.config and app.config["SECRET_KEY"]
    ):
        msg = (
            "No secret key. "
            "Generate a secret key with the command 'flask key generate'"
        )
        app.logger.error(msg)
        print(msg, file=sys.stderr)
        sys.exit(1)
