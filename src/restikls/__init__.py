# File: src/restikls/__init__.py

"""
Main application file for the Flask web server.

This file sets up the Flask app, configures it, registers blueprints,
and defines necessary hooks. It uses the application factory pattern.
"""

import logging
import sys
import warnings

from flask import Flask

if sys.version_info >= (3, 11):
    import tomllib
else:
    logging.warning(
        "Python version less than 3.11. Built-in 'tomllib' library not available."
    )
    logging.info("Attempting to import 'tomli' library.")
    try:
        import tomli as tomllib  # type: ignore[unresolved-import]
    except ImportError:
        ERROR_MESSAGE = (
            "Python version less than 3.11 and 'tomli' not installed. "
            "Either: \n"
            "1. Use Python 3.11 or higher, or\n"
            "2. Install tomli using: 'pip install tomli'"
        )
        logging.error(ERROR_MESSAGE)
        print(ERROR_MESSAGE, file=sys.stderr)
        sys.exit(1)

try:
    from flask_caching import Cache

    CACHE_AVAILABLE: bool = True
except ImportError:
    CACHE_AVAILABLE: bool = False
    logging.info("'flask_caching' library not installed.")
    warnings.warn("'flask_caching' library not installed.")

from .defaults import DefaultConfig
from .lib.bootstrap import (
    load_config_from_env,
    register_blueprints,
    register_hooks_processors,
    setup_secret,
)
from .lib.filters import register_filters
from .lib.logging import setup_logging

cache: Cache | None
if CACHE_AVAILABLE and 'Cache' in globals():
    # Initialize extensions but don't configure them yet.
    cache = Cache()


def create_app(config_filename: str=DefaultConfig.CONFIG_FILE_NAME) -> Flask:
    """
    Creates and configures an instance of the Flask application.
    This is the application factory.

    Args:
        config_filename (str, optional): The name of the configuration file.
                                         Defaults to "config.toml".

    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(__name__)

    # --- Load Configuration ---
    # Load default configuration values from the DefaultConfig class.
    try:
        app.config.from_object(DefaultConfig)
    except Exception as e:
        app.logger.error(f"Error occurred while loading default configuration: {e}")
        raise
    # Load configuration from the TOML file.
    # The `silent=True` argument can be useful if the file is optional.
    try:
        app.config.from_file(config_filename, load=tomllib.load, text=False)
    except FileNotFoundError:
        # Handle cases where the config file is missing if necessary.
        app.logger.warning(
            f"Configuration file '{config_filename}' not found. Using defaults."
        )
    except tomllib.TOMLDecodeError:
        app.logger.error(f"Invalid TOML format in '{config_filename}'. Using defaults.")
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error while loading config: {e}")
        raise
    # Override config with environment variables
    load_config_from_env(app)

    # --- Setup and Initialization ---

    # 1. Setup logging before doing anything else.
    setup_logging(app)

    # 2. Setup secret key
    setup_secret(app)

    # 3. Initialize extensions with the app instance.
    if CACHE_AVAILABLE and cache:
        cache.init_app(app)

    # 4. Register custom Jinja2 filters.
    register_filters(app)

    # 5. --- Register Blueprints ---
    register_blueprints(app)

    # 6. --- Register Hooks and Processors ---
    register_hooks_processors(app)

    app.logger.info("Application setup complete.")
    return app

def main() -> None:
    # Create the app using the factory.
    flask_app = create_app()
    # Use debug=True only for development. It should be False in production.
    # The debug flag can also be loaded from the config file.
    is_debug = flask_app.config.get("DEBUG", True)
    flask_app.run(debug=is_debug)

# This block is for running the app in a development environment.
# In production, a WSGI server like Gunicorn or uWSGI would be used.
if __name__ == "__main__":
    main()

