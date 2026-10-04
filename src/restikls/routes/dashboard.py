# File: src/restikls/routes/dashboard.py
"""Dashboard routes and error handlers."""

from flask import Blueprint, Response, current_app, g, jsonify, render_template, request

from ..lib.exceptions import ResticServiceError
from ..lib.utils import handle_api_error
from ..models.backends import determine_backend_type
from .config_routes import cred_required

bp: Blueprint = Blueprint("dashboard", __name__, url_prefix="/")

TEMPLATE = "dashboard/restic.html"
# --- Error Handlers for this Blueprint ---


@bp.errorhandler(ResticServiceError)
def handle_service_error(error: ResticServiceError) -> tuple[str | Response, int]:
    """Handles ResticServiceError exceptions"""
    current_app.logger.error(f"Dashboard service error: {error.message}")
    if request.path.startswith("/api/"):
        return handle_api_error(error.message, error.status_code)
    _template = TEMPLATE
    return render_template(_template, error_message=error.message), error.status_code


@bp.errorhandler(Exception)
def handle_generic_exception(error: Exception) -> tuple[str | Response, int]:
    """Handles unexpected exceptions"""
    current_app.logger.exception(f"Unexpected dashboard error: {str(error)}")
    message = "An unexpected internal error occurred."
    if request.path.startswith("/api/"):
        return handle_api_error(message, 500)
    _template = TEMPLATE
    return render_template(_template, error_message=message), 500


# --- Routes ---


@bp.route("/")
@cred_required
def index() -> str:
    """Renders the main dashboard page with repository statistics."""
    # stats = g.restic_service.get_repo_stats()
    # stats = get_repo_stats(config)
    # stats = json.loads(
    # '{"total_size":2142269132,"total_uncompressed_size":5007642089,
    # "compression_ratio":2.337541074647758,"compression_progress":100,
    # "compression_space_saving":57.2200030687936,"total_blob_count":138067,
    # "snapshots_count":239}')
    repo_path = (
        g.restic_service.repo_cred.repo_path
        if getattr(g, "restic_service", None)
        and hasattr(g.restic_service, "repo_cred")
        and isinstance(getattr(g.restic_service.repo_cred, "repo_path", None), str)
        else g.repo_cred.repo_path
    )
    repo_info = {
        "repo_path": repo_path,
        "backend_type": determine_backend_type(repo_path).value,
        "has_ssh_key": bool(g.repo_cred.ssh_key),
    }
    _template = TEMPLATE
    return render_template(_template, repo_info=repo_info)


@bp.route("/api/stats")
@cred_required
def api_stats() -> Response:
    """Provides repository statistics as a JSON API endpoint."""
    stats = g.restic_service.get_repo_stats()
    # stats = get_repo_stats(config)
    return jsonify(stats)


@bp.route("/health")
def health() -> tuple[dict, int]:
    """Health check endpoint for the dashboard blueprint."""
    return {"status": "healthy"}, 200
