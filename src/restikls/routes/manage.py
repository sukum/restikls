# File: src/restikls/routes/manage.py
"""Routes for managing the application."""

from flask import Blueprint, Response, current_app, g, jsonify, render_template

from .config_routes import cred_required

bp: Blueprint = Blueprint("manage", __name__)

# --- Error Handlers for this Blueprint ---


@bp.errorhandler(Exception)
def handle_generic_exception(error: Exception) -> tuple[str, int]:
    """Handles generic exceptions for the 'manage' blueprint."""
    current_app.logger.exception(str(error))
    return render_template(
        "manage/index.html", error_message=str(error), status_code=500
    ), 500


# --- Routes ---


@bp.route("/manage/")
@cred_required
def index() -> str:
    """Renders the index page for the manage blueprint."""
    return render_template("manage/index.html", result={"init": "index page"})

# Need to add superadmin auth to this route
@bp.route("/manage/config")
@cred_required
def read_config() -> str | Response:
    """Reads and returns the application configuration."""
    if _config := current_app.config:
        _config = {str(index): key for index, key in enumerate(_config)}
        return jsonify(_config)
    return render_template(
        "manage/index.html", error_message="loading config.toml failed"
    )

@bp.route("/manage/cache/stats")
@cred_required
def cache_stats() -> str | Response:
    """Lists the cache entry stats of the current repository."""
    # Scoped to the current repo_cred's cache namespace, not the whole cache.
    stats = g.cache_service.stats()
    return jsonify(stats)

# Need to add superadmin auth to this route
@bp.route("/manage/cache/clear", methods=["POST"])
@cred_required
def cache_clear() -> Response:
    """Clears the cache entries of the current repository."""
    # Scoped to the current repo_cred's cache namespace, not the whole cache.
    if g.cache_service.clear():
        return jsonify({"message": "success"})
    return jsonify({"message": "failed"})

