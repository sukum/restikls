# File: src/restikls/routes/key.py
"""Routes and error handlers for key management in the Restic UI."""

from flask import Blueprint, current_app, g, render_template

from ..lib.exceptions import KeyNotFoundError, ResticServiceError
from .config_routes import cred_required

bp: Blueprint = Blueprint("key", __name__)

# --- Error Handlers for this Blueprint ---


@bp.errorhandler(KeyNotFoundError)
def handle_key_not_found(error: KeyNotFoundError) -> tuple[str, int]:
    """Handle errors when a key is not found."""
    current_app.logger.warning(error.message)
    return render_template(
        "error.html", error_message=error.message, status_code=404
    ), 404


@bp.errorhandler(ResticServiceError)
def handle_service_error(error: ResticServiceError) -> tuple[str, int]:
    """Handle general Restic service errors for key operations."""
    current_app.logger.error(f"Key management error: {error.message}")
    return render_template(
        "key/list.html", error_message=error.message
    ), error.status_code


# --- Routes ---


@bp.route("/keys")
@cred_required
def list_keys() -> str:
    """Display a list of all keys."""
    keys = g.restic_service.get_keys()
    return render_template("key/list.html", keys=keys)


@bp.route("/key/<key_id>")
@cred_required
def key_detail(key_id: str) -> str:
    """Show details for a specific key."""
    key = g.restic_service.get_key(key_id)
    return render_template("key/detail.html", key=key)
