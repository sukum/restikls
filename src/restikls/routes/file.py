# File: src/restikls/routes/file.py
"""Routes and error handlers for file-related operations."""

import os
from io import BytesIO

from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    jsonify,
    render_template,
    request,
    send_file,
    url_for,
)

from ..lib.exceptions import (
    FileContentError,
    FileSizeError,
    ResticServiceError,
    SnapshotNotFoundError,
)
from ..lib.utils import handle_api_error, pagination_info, slice_paged_data
from .config_routes import cred_required

json_routes = [
    "/file/view",
    "/file/download",
]

bp: Blueprint = Blueprint("file", __name__)

# --- Centralized Exception Handlers for this Blueprint ---


@bp.errorhandler(SnapshotNotFoundError)
def handle_snapshot_not_found(error: SnapshotNotFoundError) -> tuple[str, int]:
    """Error handler for SnapshotNotFoundError."""
    current_app.logger.warning(f"Snapshot not found: {error.message}")
    # Render a user-friendly "Not Found" page
    return render_template(
        "error.html", error_message=error.message, status_code=error.status_code
    ), error.status_code


@bp.errorhandler(ResticServiceError)
def handle_restic_service_error(
    error: ResticServiceError,
) -> tuple[str | Response, int]:
    """A generic handler for all custom ResticService errors."""
    current_app.logger.error(f"A service error occurred: {error.message}")

    # Check if the request expects JSON (API call) or HTML
    is_api_request = request.is_json or request.path in json_routes

    if is_api_request:
        return handle_api_error(error.message, error.status_code)
    if g.is_ajax:
        return render_template(
            "error.ajax.html", error_message=error.message, status_code=500
        ), 500
    # For full page loads, render a user-friendly error page
    return render_template(
        "error.html", error_message=error.message, status_code=error.status_code
    ), error.status_code


@bp.errorhandler(Exception)
def handle_generic_exception(error: Exception) -> tuple[str | Response, int]:
    """Catch-all for any other unexpected exceptions."""
    current_app.logger.exception(f"An unexpected error occurred: {str(error)}")
    message = "An unexpected internal error occurred. Please check the logs."
    is_api_request = request.is_json or request.path in json_routes

    if is_api_request:
        return handle_api_error(message, 500)
    if g.is_ajax:
        return render_template(
            "error.ajax.html", error_message=message, status_code=500
        ), 500
    return render_template("error.html", error_message=message, status_code=500), 500


# --- Simplified Routes ---


@bp.route("/files/snapshot/<snapshot_id>")
@cred_required
def snapshot_files(snapshot_id: str) -> str:
    """
    Displays the list of files for a given snapshot.
    Supports pagination and search functionality.
    Renders either a full page or an AJAX table based on the request type.
    """
    _template = "snapshot/files.table.html" if g.is_ajax else "snapshot/files.html"
    page = int(request.args.get("page", 1))
    search = request.args.get("search", "")

    snapshot, files = g.restic_service.get_snapshot_files(snapshot_id)

    if search:
        files = [f for f in files if search.lower() in f["path"].lower()]

    records_per_page, record_count, total_pages = pagination_info(files)
    params = {
        "files": slice_paged_data(files, page),
        "is_ajax": g.is_ajax,
        "page": page,
        "record_count": record_count,
        "search": search,
        "snapshot": snapshot,
        "snapshot_id": snapshot_id,
        "total_pages": total_pages,
        "_url": url_for("file.snapshot_files", snapshot_id=snapshot_id, search=search),
    }
    return render_template(_template, **params)
    # current_app.logger.error(f"Error loading snapshot files: {str(e)}")


@bp.route("/file/history")
@cred_required
def file_history() -> str:
    """
    Displays the history of a specific file across snapshots.
    Supports pagination, search, and AJAX rendering.
    """
    _template = "file/history.table.html" if g.is_ajax else "file/history.html"
    file_path = request.args.get("file_path", "")
    page = int(request.args.get("page", 1))
    parent_page = int(request.args.get("parent_page", 1))
    paths = request.args.getlist("paths")
    search = request.args.get("search", "")
    snapshot_id = request.args.get("snapshot_id")

    files = []
    if file_path:
        files = g.restic_service.get_file_history(file_path, paths)
        files.sort(key=lambda x: x["matches"][0]["mtime"], reverse=True)

    records_per_page, record_count, total_pages = pagination_info(files)
    params = {
        "file_path": file_path,
        "files": slice_paged_data(files, page),
        "is_ajax": g.is_ajax,
        "page": page,
        "parent_page": parent_page,
        "paths": paths,
        "record_count": record_count,
        "search": search,
        "snapshot_id": snapshot_id,
        "total_pages": total_pages,
        "_url": url_for(
            "file.file_history", file_path=file_path, paths=paths, search=search
        ),
    }
    return render_template(_template, **params)
    # current_app.logger.error(f"Error loading snapshot file history: {str(e)}")


@bp.route("/file/download", methods=["POST"])
@cred_required
def file_download() -> Response:
    """
    Downloads a specific file from a snapshot as an attachment.
    Returns the file as a binary stream with appropriate headers.
    """
    data = request.get_json()
    file_path = data["file_path"]
    snapshot_id = data["snapshot_id"]

    file_name = os.path.basename(file_path)
    file_download_maxsize = current_app.config[
        "FILE_DOWNLOAD_MAXSIZE"
    ]

    # Fetch file metadata and check size
    file_metadata = g.restic_service.file_metadata(snapshot_id, file_path)
    file_size = int(file_metadata["size"])
    if file_size > file_download_maxsize:
        raise FileSizeError(filesize=file_size, maximum_allowed=file_download_maxsize)
    # Get file
    file_bytes = g.restic_service.dump_file(snapshot_id, file_path)
    # Confirm size of file
    file_size = len(file_bytes)
    if file_size > file_download_maxsize:
        raise FileSizeError(filesize=file_size, maximum_allowed=file_download_maxsize)

    return send_file(
        BytesIO(file_bytes),
        as_attachment=True,
        download_name=file_name,
        # Force download
        mimetype="application/octet-stream",
    )
    # current_app.logger.error(f"Error during file download: {msg}")


@bp.route("/file/view")
@cred_required
def file_view() -> Response:
    """
    Returns the contents of a specific file from a snapshot as JSON.
    Decodes the file as UTF-8 text; raises FileContentError if decoding fails.
    """
    # return jsonify(error="test error"), 500
    file_path = request.args.get("file_path", "")
    snapshot_id = request.args.get("snapshot_id")

    file_name = os.path.basename(file_path)
    file_view_maxsize = current_app.config["FILE_VIEW_MAXSIZE"]

    # Fetch file metadata and check size
    file_metadata = g.restic_service.file_metadata(snapshot_id, file_path)
    file_size = int(file_metadata["size"])
    if file_size > file_view_maxsize:
        raise FileSizeError(filesize=file_size, maximum_allowed=file_view_maxsize)
    # Get file
    file_bytes = g.restic_service.dump_file(snapshot_id, file_path)
    # Confirm size of file
    file_size = len(file_bytes)
    if file_size > file_view_maxsize:
        raise FileSizeError(filesize=file_size, maximum_allowed=file_view_maxsize)

    try:
        # Convert to bytes
        file_data = file_bytes.decode("utf-8")
        return jsonify(
            {
                "file_name": file_name,
                "file_path": file_path,
                "file_data": file_data,
            }
        )
    except UnicodeDecodeError as e:
        # This is a specific error about the file content, not the service itself.
        # We can raise our custom exception here to be caught by our handler.
        raise FileContentError() from e
