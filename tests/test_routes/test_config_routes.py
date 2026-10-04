# File: tests/test_routes/test_config_routes.py
import os
from unittest.mock import ANY, Mock

from flask import g, url_for

from restikls.routes import config_routes


def test_cred_required_decorator_with_cred(
    app, client, monkeypatch, mock_app_config
):
    # patched in conftest fixture
    from restikls.lib.config import get_repo_cred

    monkeypatch.setattr("restikls.routes.config_routes.get_repo_cred", get_repo_cred)

    # Define a mock route to test the decorator
    @app.route("/protected")
    @config_routes.cred_required
    def protected_view():
        return f"Config path: {g.repo_cred.repo_path}"

    response = client.get("/protected")
    assert response.status_code == 200
    assert b"Config path: /repo" in response.data


def test_cred_required_decorator_no_cred(app, client, monkeypatch):
    # Mock get_repo_cred to return None
    monkeypatch.setattr(
        "restikls.routes.config_routes.get_repo_cred", Mock(return_value=None)
    )
    monkeypatch.setattr("restikls.lib.config.get_repo_cred", Mock(return_value=None))
    monkeypatch.setattr(
        "restikls.lib.bootstrap._config.get_repo_cred", Mock(return_value=None)
    )

    # Define a mock route
    @app.route("/mock_route")
    @config_routes.cred_required
    def mock_view():
        return {"repo_cred": g.repo_cred}

    response = client.get("/mock_route")
    assert response.status_code == 302
    with app.test_request_context():
        assert response.location.endswith(
            url_for("config_routes.config", _external=False)
        )


def test_config_get_no_config(client, monkeypatch):
    # Mock get_repo_cred to return None
    monkeypatch.setattr(
        "restikls.routes.config_routes.get_repo_cred", Mock(return_value=None)
    )
    # monkeypatch.setattr("restikls.lib.config.get_repo_cred", Mock(return_value=None))

    response = client.get("/config")
    assert response.status_code == 200
    assert b"repo_path" in response.data  # Check template rendering


def test_config_get_with_config(client, monkeypatch):
    from restikls.lib.config import get_repo_cred

    mock_response = Mock(side_effect=get_repo_cred)
    monkeypatch.setattr("restikls.lib.bootstrap._config.get_repo_cred", mock_response)
    response = client.get("/config")
    assert response.status_code == 200
    # print(get_repo_cred())
    mock_response.assert_called()
    assert b"/repo" in response.data
    # Assuming repo_key added
    assert b"available" in response.data


def test_config_post_success(app, client, monkeypatch):
    # Mock set_config and get_repo_cred
    mock_response = Mock()
    monkeypatch.setattr("restikls.routes.config_routes.set_config", mock_response)
    monkeypatch.setattr(
        "restikls.routes.config_routes.get_repo_cred", Mock(return_value=None)
    )
    monkeypatch.setattr(
        "restikls.routes.config_routes.BaseBackend.validate", Mock(return_value=None)
    )
    monkeypatch.setattr(
        "restikls.routes.config_routes.validate_repository",
        Mock(return_value=(True, None)),
    )
    form_data = {
        "repo_path": "/repo",
        "repo_key": "key123",
    }
    with app.app_context():
        response = client.post("/config", data=form_data, follow_redirects=False)
        assert response.status_code == 302
        assert response.location.endswith(url_for("dashboard.index", _external=False))
        mock_response.assert_called_with(ANY, "/repo", "key123", None)


def test_config_post_error(client, monkeypatch):
    # Mock set_config to raise an exception
    monkeypatch.setattr(
        "restikls.routes.config_routes.set_config",
        Mock(side_effect=Exception("Config error")),
    )
    monkeypatch.setattr(
        "restikls.routes.config_routes.get_repo_cred", Mock(return_value=None)
    )
    monkeypatch.setattr(
        "restikls.routes.config_routes.BaseBackend.validate", Mock(return_value=None)
    )
    monkeypatch.setattr(
        "restikls.routes.config_routes.validate_repository",
        Mock(return_value=(True, None)),
    )

    form_data = {"repo_path": "/repo", "repo_key": "key123"}
    response = client.post("/config", data=form_data)
    assert response.status_code == 500
    assert b"unexpected internal error" in response.data  # Error message in template


# relative paths, root dir, invalid path
def test_config_post_invalid_repo_paths(app, client, monkeypatch):
    # Mock set_config and get_repo_cred
    mock_response = Mock()
    monkeypatch.setattr("restikls.routes.config_routes.set_config", mock_response)
    # monkeypatch.setattr("restikls.routes.config_routes.get_repo_cred", Mock(return_value=None))
    monkeypatch.setattr(
        "restikls.lib.bootstrap._config.get_repo_cred", Mock(return_value=None)
    )
    # monkeypatch.setattr("restikls.routes.config_routes.validate_file_path", Mock(return_value=None))
    # monkeypatch.setattr("restikls.routes.config_routes.validate_repository", Mock(return_value=(True, None)))

    form_data = {
        "repo_path": "..",
        "repo_key": "key123",
    }
    with app.app_context():
        # relative path
        response = client.post("/config", data=form_data, follow_redirects=False)
        assert response.status_code == 400
        mock_response.assert_not_called()
        # root dir
        form_data["repo_path"] = "/"
        response = client.post("/config", data=form_data, follow_redirects=False)
        assert response.status_code == 400
        # invalid path
        form_data["repo_path"] = "/invalid-path"
        response = client.post("/config", data=form_data, follow_redirects=False)
        assert response.status_code == 400
        # file and not a dir
        form_data["repo_path"] = __file__
        response = client.post("/config", data=form_data, follow_redirects=False)
        assert response.status_code == 400
        # empty path with ssh_key (regression test for LocalBackend TypeError)
        form_data["repo_path"] = ""
        form_data["ssh_key"] = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
        response = client.post("/config", data=form_data, follow_redirects=False)
        assert response.status_code == 400


# valid path, but not a repository
def test_config_post_invalid_repository(app, client, monkeypatch):
    # Mock set_config and get_repo_cred
    mock_response = Mock()
    monkeypatch.setattr("restikls.routes.config_routes.set_config", mock_response)
    # monkeypatch.setattr("restikls.routes.config_routes.get_repo_cred", Mock(return_value=None))
    monkeypatch.setattr(
        "restikls.lib.bootstrap._config.get_repo_cred", Mock(return_value=None)
    )
    # monkeypatch.setattr(
    #     "restikls.routes.config_routes.validate_file_path", Mock(return_value=None)
    # )
    # monkeypatch.setattr("restikls.routes.config_routes.validate_repository", Mock(return_value=(True, None)))

    current_dir = os.path.dirname(os.path.abspath(__file__))
    form_data = {
        "repo_path": current_dir,
        "repo_key": "key123",
    }
    with app.app_context():
        # relative path
        response = client.post("/config", data=form_data, follow_redirects=False)
        print(response.data)
        assert response.status_code == 400
        mock_response.assert_not_called()
        assert b"unable to open config file" in response.data


def test_logout_success(app, client, monkeypatch):
    # Mock clear_config
    mock_response = Mock()
    monkeypatch.setattr("restikls.routes.config_routes.clear_config", mock_response)

    with app.app_context():
        response = client.post("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.location.endswith(
            url_for("config_routes.config", _external=False)
        )
        mock_response.assert_called()


def test_logout_error(app, client, monkeypatch):
    # Mock clear_config to raise an exception
    monkeypatch.setattr(
        "restikls.routes.config_routes.clear_config",
        Mock(side_effect=Exception("Logout error")),
    )

    with app.app_context():
        response = client.post("/logout", follow_redirects=False)
        assert response.status_code == 500
        assert (
            b"unexpected internal error" in response.data
        )  # Error message in template
