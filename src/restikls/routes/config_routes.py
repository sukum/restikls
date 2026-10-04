# File: src/restikls/routes/config_routes.py
"""
Routes and error handlers for repository configuration.
This module provides:
- Error handlers for configuration-related exceptions.
- A decorator to ensure repository configuration is present before accessing certain routes.
- Routes for displaying, updating, and clearing repository configuration,
  including support for SFTP and SSH key validation.
"""

from functools import wraps
from typing import Any, Callable, TypedDict

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)


from ..lib.config import clear_config, get_repo_cred, set_config
from ..lib.exceptions import ConfigurationError
from ..models.credentials import ResticCredentials
from ..models.backends import BackendInput, BaseBackend, get_repo_scheme
from ..services.validator_service import repository as validate_repository

bp: Blueprint = Blueprint("config_routes", __name__)

class ViewData(TypedDict):
    repo_path: str
    has_key: bool
    has_ssh_key: bool


# --- Error Handlers for this Blueprint ---


@bp.errorhandler(ConfigurationError)
def handle_configuration_error(error: ConfigurationError) -> tuple[str, int]:
    """Handles validation errors by re-rendering the config form with an error message."""
    current_app.logger.error(f"Configuration Error: {error.message}")
    # Re-render the form with the specific error message
    error_html = str(error.message).replace("\n", "<br />")
    return render_template("config.html", error_message=error_html), error.status_code


@bp.errorhandler(Exception)
def handle_generic_exception(error: Exception) -> tuple[str, int]:
    """Catches any other unexpected exceptions during configuration."""
    current_app.logger.exception(f"Unexpected configuration error: {str(error)}")
    message = "An unexpected internal error occurred. Please check the logs."
    return render_template("config.html", error_message=message), 500


# --- Decorator and Routes ---


# Decorator to check for config
def cred_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to ensure that a repository configuration is present.

    If a valid configuration is not found in the user's session,
    it redirects them to the configuration page.
    Otherwise, it injects the loaded configuration dictionary
    as the first argument to the decorated function.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if current_app.debug:
            current_app.logger.debug("cred_required:route: %s", request.endpoint)
        # Should already be added in before_request
        # if not hasattr(g, "config") or not g.config:
        #     g.config = get_repo_cred()
        if not g.repo_cred:
            current_app.logger.info(
                "Configuration not found, redirecting to config page."
            )
            return redirect(url_for("config_routes.config"))

            # return redirect(url_for("config_routes.config"))
        return f(*args, **kwargs)

    return decorated_function


@bp.route("/config", methods=["GET", "POST"])
def config() -> Response | str:
    """
    Handles the creation and updating of the repository configuration.

    GET: Displays the configuration form.
    POST: Processes the submitted form, encrypts the key,
          and saves the configuration in session cookies.
    """
    repo_cred: ResticCredentials | None = None
    view_data: ViewData
    # For GET request
    if not hasattr(g, "repo_cred") or not g.repo_cred: # New form
        repo_cred = get_repo_cred()
    else: # Edit form
        repo_cred = g.repo_cred

    if repo_cred: #edit
        view_data = {
            "repo_path": getattr(repo_cred, "repo_path", ""),
            "has_key": bool(getattr(repo_cred, "repo_key", False)),
            "has_ssh_key": bool(getattr(repo_cred, "ssh_key", False)),
        }
    else: #new
        view_data = {"repo_path": "", "has_key": False, "has_ssh_key": False}

    if request.method == "POST":
        # 1. Extract and sanitize inputs
        repo_path = request.form["repo_path"].strip()
        form_repo_key = request.form.get("repo_key", "").strip()
        form_ssh_key = request.form.get("ssh_key", "").strip()

        # 2. Extract existing keys for merging with form data
        existing_repo_key: str = ""
        existing_ssh_key: str = ""
        if repo_cred:
            existing_repo_key = getattr(repo_cred, "repo_key", "")
            existing_ssh_key = getattr(repo_cred, "ssh_key", "")

        # 3. Merge: Use form value if provided, otherwise fallback to existing
        final_repo_key = form_repo_key if form_repo_key else existing_repo_key
        final_ssh_key = form_ssh_key if form_ssh_key else existing_ssh_key

        # 4. Pack arguments into typed backend input
        backend_input = BackendInput(
            repo_path=repo_path,
            repo_key=final_repo_key,
            ssh_key=final_ssh_key,
        )

        # 5. Instantiate backend and validate structure/format
        try:
            # get_repo_scheme uses BackendInput to route to Local, SFTP, or REST
            repo: BaseBackend = get_repo_scheme(backend_input)
            repo.validate()
        except (ValueError, TypeError) as e:
            # Handle and log the exception raised by backends.py
            current_app.logger.error("Configuration validation failed: %s", str(e))
            # Catch backend validation errors and raise as ConfigurationError
            raise ConfigurationError(str(e))
        else:
            # 6. Validate the repository by testing with Restic CLI
            # We pass the properties from the validated 'repo' object
            is_valid, err_msg = validate_repository(
                repo.repo_path,
                repo.repo_key,
                getattr(repo, "ssh_key", None)
            )
            if not is_valid or err_msg:
                raise ConfigurationError(err_msg or "Error")
            
            # 7. Success state handling
            flash("Your configuration is successfully saved in your cookie encrypted.")
            # On success, redirect to the main dashboard.
            response = make_response(redirect(url_for("dashboard.index")))
            # Save the validated configuration in session cookie
            set_config(response, repo.repo_path, repo.repo_key, getattr(repo, "ssh_key", None))
            current_app.logger.info(f"Successfully set configuration for repo: {repo.repo_path}")
            return response

    return render_template("config.html", **view_data)


@bp.route("/logout", methods=["GET", "POST"])
def logout() -> Response:
    """
    Logs the user out by clearing all configuration cookies.
    """
    response = make_response(redirect(url_for("config_routes.config")))
    clear_config(response)
    current_app.logger.info("User logged out, cookies cleared.")
    flash("You have been logged out successfully.", "info")
    return response
