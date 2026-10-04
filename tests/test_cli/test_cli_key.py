# File: tests/test_cli/test_cli_key.py

from unittest.mock import patch


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
