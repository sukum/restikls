# File: src/restikls/routes/snapshot.py
"""
Snapshot management blueprint.
"""

from flask import Blueprint, current_app, g, render_template, request, url_for

from ..lib.exceptions import ResticServiceError, SnapshotNotFoundError
from ..lib.utils import pagination_info, slice_paged_data
from .config_routes import cred_required

bp: Blueprint = Blueprint("snapshot", __name__)

# --- Error Handlers for this Blueprint ---


@bp.errorhandler(SnapshotNotFoundError)
def handle_snapshot_not_found(error: SnapshotNotFoundError) -> tuple[str, int]:
    """Handle the SnapshotNotFoundError exception"""
    current_app.logger.error(error.message)
    return render_template(
        "error.html", error_message=error.message, status_code=404
    ), 404


@bp.errorhandler(ResticServiceError)
def handle_service_error(error: ResticServiceError) -> tuple[str, int]:
    """Handle ResticServiceError exceptions"""
    current_app.logger.error(f"Snapshot error: {error.message}")
    # Determine the correct template to render based on the request
    if "snapshots" in request.path:
        template = "snapshot/list.html"
    else:
        template = "snapshot/list.table.html" if g.is_ajax else "snapshot/list.html"
    return render_template(template, error_message=error.message), error.status_code


# --- Routes ---


@bp.route("/snapshots/")
@cred_required
def list_snapshots() -> str:
    """
    List all available snapshots with optional filtering and sorting.
    Query parameters:
        page (int): The page number to display (default: 1)
        sort (str): Sort direction - 'asc' or 'desc' (default: 'desc')
        tags (str): Filter snapshots by tags
        hosts (str): Filter snapshots by hosts
    Returns:
        str: Rendered HTML template containing the snapshot list
    Raises:
        ResticServiceError: If there's an issue retrieving snapshots
    """
    _template = "snapshot/list.table.html" if g.is_ajax else "snapshot/list.html"

    page = int(request.args.get("page", 1))
    sort = request.args.get("sort", "desc")
    tags = request.args.get("tags", "").strip()
    hosts = request.args.get("hosts", "").strip()

    snapshots = g.restic_service.get_snapshots(
        filters={"tags": tags, "hosts": hosts, "sort": sort}
    )

    _records_per_page, record_count, total_pages = pagination_info(snapshots)
    params = {
        "hosts": hosts,
        "is_ajax": g.is_ajax,
        "page": page,
        "record_count": record_count,
        "snapshots": slice_paged_data(snapshots, page),
        "sort": sort,
        "tags": tags,
        "total_pages": total_pages,
        "_url": url_for("snapshot.list_snapshots", sort=sort, tags=tags, hosts=hosts),
    }
    return render_template(_template, **params)


@bp.route("/snapshot/<snapshot_id>")
@cred_required
def snapshot_detail(snapshot_id: str) -> str:
    """
    Display detailed information for a specific snapshot.
    Args:
        snapshot_id (str): The ID of the snapshot to display
    Returns:
        str: Rendered HTML template with the snapshot details
    Raises:
        SnapshotNotFoundError: If the requested snapshot doesn't exist
    """
    snapshots = g.restic_service.get_snapshot(snapshot_id=snapshot_id)
    if not snapshots:
        raise SnapshotNotFoundError(snapshot_id)
    return render_template("snapshot/detail.html", snapshot=snapshots[0])
