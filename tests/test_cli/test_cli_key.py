# File: tests/test_cli/test_cli_key.py

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from restikls import create_app
from restikls.cli.key import bp


@pytest.mark.parametrize("env_override", [False, True])
def test_generate_if_missing_uses_config_and_preserves_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env_override: bool
) -> None:
    # Arrange: load a real TOML setting, optionally overridden by the environment.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["flask", "key", "generate", "--if-missing"])
    monkeypatch.delenv("RESTIKLS_KEY_FILE", raising=False)
    config_key = tmp_path / "configured.key"
    selected_key = tmp_path / "override.key" if env_override else config_key
    config_file = tmp_path / "config.toml"
    config_file.write_text(f'KEY_FILE = "{config_key.as_posix()}"\n', encoding="utf-8")
    if env_override:
        monkeypatch.setenv("RESTIKLS_KEY_FILE", str(selected_key))
    app = create_app(config_filename=str(config_file))
    runner = app.test_cli_runner()
    assert not selected_key.exists()

    # Act: simulate initial startup and a subsequent startup.
    first = runner.invoke(args=["key", "generate", "--if-missing"])
    assert first.exit_code == 0, first.output
    original_key = selected_key.read_bytes()
    Fernet(original_key)
    second = runner.invoke(args=["key", "generate", "--if-missing"])

    # Assert: preserve the selected key and never prompt or create another key.
    assert second.exit_code == 0, second.output
    assert selected_key.read_bytes() == original_key
    assert "Skipping generation." in second.output
    assert "Overwrite?" not in second.output
    assert not (tmp_path / "secret.key").exists()
    if env_override:
        assert not config_key.exists()


def test_generate_if_missing_write_failure(tmp_path: Path) -> None:
    # Arrange: the destination's parent directory does not exist.
    app = Flask(__name__)
    app.config["KEY_FILE"] = str(tmp_path / "missing" / "secret.key")
    app.register_blueprint(bp)

    # Act / Assert: let the write error propagate to fail container startup.
    with pytest.raises(RuntimeError, match="could not be written"):
        app.test_cli_runner().invoke(
            args=["key", "generate", "--if-missing"], catch_exceptions=False
        )


def test_generate_if_missing_rejects_force(tmp_path: Path) -> None:
    # Arrange: an existing key must survive conflicting command options.
    key_file = tmp_path / "secret.key"
    original_key = Fernet.generate_key()
    key_file.write_bytes(original_key)
    app = Flask(__name__)
    app.config["KEY_FILE"] = str(key_file)
    app.register_blueprint(bp)

    # Act.
    result = app.test_cli_runner().invoke(
        args=["key", "generate", "--if-missing", "--force"]
    )

    # Assert.
    assert result.exit_code == 2
    assert "cannot be used together" in result.output
    assert key_file.read_bytes() == original_key


def test_generate_command_new(runner):
    """Test 'flask key generate' when no key exists."""
    with (
        patch("os.path.exists", return_value=False) as mock_exists,
        patch("restikls.cli.key.generate_new_key", return_value=True) as mock_generate,
    ):
        result = runner.invoke(args=["key", "generate"])

        assert result.exit_code == 0
        mock_exists.assert_called()
        mock_generate.assert_called_once()
        assert (
            "secret.key" in mock_generate.call_args[0][0]
        )  # Checks logger call inside


def test_generate_command_aborts_on_existing(runner):
    """Test 'flask key generate' aborts if user says no to overwrite."""
    with (
        patch("os.path.exists", return_value=True),
        patch("restikls.cli.key.generate_new_key") as mock_generate,
        patch("builtins.input", return_value="n"),
    ):
        result = runner.invoke(args=["key", "generate"])

        print(result)
        assert result.exit_code == 0
        assert "Aborted key generation." in result.output
        mock_generate.assert_not_called()


def test_generate_command_force_overwrites(runner):
    """Test 'flask key generate --force' overwrites an existing key."""
    with (
        patch("os.path.exists", return_value=True),
        patch("restikls.cli.key.generate_new_key", return_value=True) as mock_generate,
    ):
        result = runner.invoke(args=["key", "generate", "--force"])

        assert result.exit_code == 0
        mock_generate.assert_called_once()


def test_generate_command_fails(runner):
    """Test 'flask key generate' when the generation function fails."""
    with (
        patch("os.path.exists", return_value=False),
        patch("restikls.cli.key.generate_new_key", return_value=False),
        patch("sys.exit") as mock_exit,
    ):
        result = runner.invoke(args=["key", "generate"])

        # The exit code from sys.exit is captured by the Click test runner
        assert result.exit_code == 0
        mock_exit.assert_called()


def test_print_command(runner):
    """Test 'flask key print' command."""
    test_key = "this-is-a-test-key"
    with patch(
        "restikls.cli.key.read_key", return_value=test_key.encode("utf-8")
    ) as mock_read:
        result = runner.invoke(args=["key", "print"])

        assert result.exit_code == 0
        assert test_key in result.output
        mock_read.assert_called_once()


def test_print_command_read_error(runner):
    """Test 'flask key print' when reading the key fails."""
    with patch(
        "restikls.cli.key.read_key", side_effect=RuntimeError("File not found")
    ) as mock_read:
        result = runner.invoke(args=["key", "print"])

        # Click runner catches the exception and exits with a non-zero status
        assert result.exit_code != 0
        # The original exception is available in the result object
        assert isinstance(result.exception, RuntimeError)
        assert "File not found" in str(result.exception)
        mock_read.assert_called_once()
