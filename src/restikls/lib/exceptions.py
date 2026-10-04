# File: src/restikls/lib/exceptions.py
"""
Custom exception classes.
Provides specialized exceptions for handling restic operations, file access,
and configuration related errors, each with appropriate HTTP status codes.
"""


class ResticServiceError(Exception):
    """Base exception for all Restic service related errors."""

    def __init__(self, message: str, status_code: int=500) -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: int = status_code


class SnapshotNotFoundError(ResticServiceError):
    """Raised when a specific snapshot ID cannot be found."""

    def __init__(self, snapshot_id: str) -> None:
        message = f"Snapshot with ID '{snapshot_id}' could not be found."
        super().__init__(message, status_code=404)


class KeyNotFoundError(ResticServiceError):
    """Raised when a specific key ID cannot be found."""

    def __init__(self, key_id: str) -> None:
        message = f"Key with ID '{key_id}' could not be found."
        super().__init__(message, status_code=404)


class ResticTimeoutError(ResticServiceError):
    """Raised when a restic command times out during execution."""

    def __init__(self, message: str="Restic command timed out while running.") -> None:
        super().__init__(message, status_code=500)


class FileAccessError(ResticServiceError):
    """Raised when a file cannot be dumped or accessed from a snapshot."""

    def __init__(self, message: str="Could not access or restore the requested file.") -> None:
        super().__init__(message, status_code=500)


class FileContentError(ResticServiceError):
    """Raised when file content cannot be processed as expected (e.g., decoding)."""

    def __init__(
        self, message: str="File content is binary or could not be decoded to text."
    ) -> None:
        # Bad Request, as the user asked for a text view of a binary file.
        super().__init__(message, status_code=400)


class FileSizeError(ResticServiceError):
    """Raied when file size exceeds configured maximum."""

    def __init__(
        self,
        message: str="Filesize exceeds configured maximum.",
        filesize: int | None=None,
        maximum_allowed: int | None=None,
    ) -> None:
        if filesize and maximum_allowed:
            message = (
                f"{message} Filesize: {filesize}, Maximum allowed: {maximum_allowed}"
            )
        super().__init__(message, status_code=400)


class ConfigurationError(Exception):
    """Base exception for configuration and validation errors."""

    def __init__(self, message: str, status_code: int=400) -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: int = status_code


class ResticValidationError(ResticServiceError):
    """Raised when Restic CLI JSON output fails boundary validation."""

    def __init__(self, message: str = "Invalid or malformed data received from restic.") -> None:
        super().__init__(message, status_code=500)

