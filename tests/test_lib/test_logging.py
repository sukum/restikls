# File: tests/test_lib/test_logging.py
import logging
import os
from unittest.mock import MagicMock

from restikls.lib.logging import configure_log_handler, create_log_directory


def test_setup_logging(app, tmp_path):
    """Test that logging is configured correctly."""
    log_dir = tmp_path / "test_logs"
    log_file_path = log_dir / "test_app.log"

    # Configure the app to use the temporary log directory
    app.config["LOG_DIRECTORY"] = str(log_dir)
    app.config["LOG_FILENAME"] = "test_app.log"
    app.config["LOG_LEVEL"] = "info"

    # Run the setup function
    from restikls.lib.logging import setup_logging

    setup_logging(app)

    assert log_dir.exists()
    assert log_file_path.exists()

    # Check that a handler was added and the level was set
    assert len(app.logger.handlers) > 0
    import logging

    assert app.logger.level == logging.INFO


# --- Tests for create_log_directory ---


def test_create_log_directory_when_dir_does_not_exist(monkeypatch):
    """
    Test that the directory is created if it does not exist.
    """
    # Arrange: Keep track of calls to our mock makedirs
    makedirs_calls = []

    # Use monkeypatch to replace os.path.exists and os.makedirs
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    monkeypatch.setattr(os, "makedirs", lambda path: makedirs_calls.append(path))

    log_dir = "/tmp/test_logs"

    # Act
    result = create_log_directory(log_dir)

    # Assert
    assert result is True
    assert makedirs_calls == [log_dir]


def test_create_log_directory_when_dir_already_exists(monkeypatch):
    """
    Test that os.makedirs is not called if the directory already exists.
    """
    # Arrange
    makedirs_calls = []
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    monkeypatch.setattr(os, "makedirs", lambda path: makedirs_calls.append(path))

    log_dir = "/tmp/existing_logs"

    # Act
    result = create_log_directory(log_dir)

    # Assert
    assert result is True
    assert not makedirs_calls  # Check that the list is empty


def test_create_log_directory_os_error_on_creation(monkeypatch, caplog):
    """
    Test that the function returns False and logs an error on OSError.
    """

    # Arrange: Create a mock function that raises an OSError
    def mock_makedirs_raises_os_error(path):
        raise OSError("Permission denied")

    monkeypatch.setattr(os.path, "exists", lambda path: False)
    monkeypatch.setattr(os, "makedirs", mock_makedirs_raises_os_error)

    log_dir = "/root/no_permission_logs"

    # Act
    with caplog.at_level(logging.ERROR):
        result = create_log_directory(log_dir)

    # Assert
    assert result is False
    assert "Error creating log directory" in caplog.text
    assert "Permission denied" in caplog.text


def test_create_log_directory_unexpected_error(monkeypatch, caplog):
    """
    Test that the function returns False and logs on an unexpected exception.
    """

    # Arrange: Create a mock function that raises a generic Exception
    def mock_exists_raises_exception(path):
        raise Exception("Something went wrong")

    monkeypatch.setattr(os.path, "exists", mock_exists_raises_exception)

    log_dir = "/tmp/any_log_dir"

    # Act
    with caplog.at_level(logging.ERROR):
        result = create_log_directory(log_dir)

    # Assert
    assert result is False
    assert "Unexpected error creating log directory" in caplog.text
    assert "Something went wrong" in caplog.text


# --- Tests for configure_log_handler ---


def test_configure_log_handler_success(monkeypatch):
    """
    Test successful configuration of the RotatingFileHandler.
    """
    # Arrange: Create mock instances and factories to track calls
    mock_handler_instance = MagicMock()
    mock_formatter_instance = MagicMock()

    # This factory will be called instead of the real RotatingFileHandler class
    # It allows us to check the arguments passed to the constructor (__init__)
    handler_factory = MagicMock(return_value=mock_handler_instance)
    formatter_factory = MagicMock(return_value=mock_formatter_instance)

    monkeypatch.setattr("restikls.lib.logging.RotatingFileHandler", handler_factory)
    monkeypatch.setattr("restikls.lib.logging.logging.Formatter", formatter_factory)

    log_path = "/var/log/app.log"
    max_bytes = 10 * 1024 * 1024  # 10 MB
    backup_count = 5
    expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Act
    handler = configure_log_handler(log_path, max_bytes, backup_count)

    # Assert
    # 1. Check that RotatingFileHandler was instantiated with correct args
    handler_factory.assert_called_once_with(
        log_path, maxBytes=max_bytes, backupCount=backup_count
    )

    # 2. Check that Formatter was instantiated with the correct format string
    formatter_factory.assert_called_once_with(expected_format)

    # 3. Check that setFormatter was called on the handler instance
    mock_handler_instance.setFormatter.assert_called_once_with(mock_formatter_instance)

    # 4. Check that the returned object is our mocked handler instance
    assert handler is mock_handler_instance


def test_configure_log_handler_exception(monkeypatch, caplog):
    """
    Test that the function returns None and logs an error if an exception occurs.
    """
    # Arrange: Replace RotatingFileHandler with a lambda that raises an error
    monkeypatch.setattr(
        "restikls.lib.logging.RotatingFileHandler",
        lambda *args, **kwargs: exec("raise Exception('Failed to open file')"),
    )

    log_path = "/invalid/path/app.log"

    # Act
    with caplog.at_level(logging.ERROR):
        handler = configure_log_handler(log_path, 1024, 5)

    # Assert
    assert handler is None
    assert "Error configuring log handler" in caplog.text
    assert "Failed to open file" in caplog.text
