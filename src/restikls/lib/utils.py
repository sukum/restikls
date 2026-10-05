# File: src/restikls/lib/utils.py
"""
Utility functions for pagination, JSON processing, timing, SSH key management,
and API error handling.
"""

import json
import os
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from itertools import islice
from pathlib import Path
from typing import NamedTuple

from flask import Response, current_app, jsonify

from ..models.credentials import ResticCredentials


class PaginationInfo(NamedTuple):
    records_per_page: int
    record_count: int
    total_pages: int

def pagination_info(data: list) -> PaginationInfo:
    """
    Returns pagination details: records per page, total records, and total pages.
    """
    records_per_page = current_app.config["PAGE_RECORDS"]
    record_count = len(data)
    # Ceiling division
    total_pages = (record_count + (records_per_page - 1)) // records_per_page
    return PaginationInfo(records_per_page, record_count, total_pages)


def slice_paged_data(data: list, page: int = 1) -> Iterator[object]:
    """
    Returns an iterator for the data items on the specified page.
    """
    # records_per_page = g.config["PAGE_RECORDS"]
    records_per_page = current_app.config["PAGE_RECORDS"]
    page = max(1, page)  # in case page is negative or 0
    start = records_per_page * (page - 1)
    stop = records_per_page * page
    return islice(data, start, stop)


def combine_json_lines(json_lines_str: str) -> str:
    """
    Converts a string of newline-separated JSON objects into a single JSON array string.

    Args:
        json_lines_str (str): A string containing one or more JSON objects,
                              each on a new line.

    Returns:
        str: A formatted JSON string representing an array of those objects.

    Raises:
        ValueError: If any line contains an invalid JSON object.
    """
    if not json_lines_str or not json_lines_str.strip():
        return "[]"

    try:
        # This is more efficient and handles empty lines gracefully with filter.
        lines = json_lines_str.split("\n")
        non_empty_lines = filter(lambda line: line.strip(), lines)
        parsed_objects = map(json.loads, non_empty_lines)
        return json.dumps(list(parsed_objects), indent=2)
    except json.JSONDecodeError as e:
        # Find the problematic line for better error logging
        problem_line = ""
        for line in json_lines_str.split("\n"):
            try:
                json.loads(line)
            except json.JSONDecodeError:
                problem_line = line
                break
        current_app.logger.error("Invalid JSON found in line: %s", problem_line)
        raise ValueError("Invalid JSON object found in output stream.") from e


"""
    # Split the string into individual JSON dicts
    dict_strings = json_lines_str.split('\n')

    # Clean up and add the missing closing brace for each dict (except last one)
    dict_strings = [s.strip() for s in dict_strings]

    # Remove any empty strings that might have been created
    # Parse each JSON string to validate it's proper JSON
    try:
        dicts = []
        for s in dict_strings:
            if s:
                dicts.append(json.loads(s))
    except json.JSONDecodeError as e:
        # Handle malformed JSON if needed
        raise ValueError(f"Invalid JSON string: {s}") from e

    # Convert the list of dicts back to a JSON array string
    json_array_string = json.dumps(dicts, indent=2)
    return json_array_string
"""


def time_process(threshold: int = 10) -> Callable:
    """
    A decorator that logs the execution time of a function if it exceeds a threshold.

    (Original name was `time_process`)

    Args:
        threshold (int, optional): The time limit in seconds. If execution
                                           time exceeds this, a warning is logged.
                                           Defaults to 10.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = f(*args, **kwargs)
            exec_time = time.time() - start_time

            if exec_time > threshold:
                current_app.logger.warning(
                    f"Function '{f.__name__}' exceeded {threshold} sec threshold."  # type: ignore
                    f"Execution time: {exec_time:.3f} secs"
                )
            return result

        return wrapper

    return decorator


@contextmanager
def manage_ssh_key_file(
    repo_cred: ResticCredentials, ssh_key_content: str | None = None
) -> Generator[str, None, None]:
    """
    Context manager to securely write an SSH key from config to a temporary file.

    This function is designed to be used with a 'with' statement. It takes the
    application config dictionary, extracts the 'ssh_key' if present, and writes
    it to a temporary file with secure permissions (read/write for owner only).
    The path to this file is yielded to the 'with' block.

    After the 'with' block exits, the temporary file is automatically and
    securely deleted. This is crucial for not leaving sensitive key material
    on the disk.

    This works inside Docker containers as it uses the standard `tempfile`
    module, which writes to the OS's temporary directory (e.g., /tmp).

    Args:
        repo_cred (ResticCredentials): The application configuration object, 
                                       which contains an 'ssh_key' entry.
        ssh_key_content (str|None): ssh_key_content directly passed in

    Yields:
        str: The absolute path to the temporary SSH key file if a key
                     was found in the config, otherwise raise ValueError.

    Example:
        with manage_ssh_key_file(g.repo_cred) as key_path:
            if key_path:
                # Use key_path in a command, e.g., ssh -i key_path
                ...
            else:
                # No key was present
                ...
        # After this block, the key file is deleted.
    """
    if not ssh_key_content:
        assert isinstance(repo_cred, ResticCredentials)
        ssh_key_content = repo_cred.ssh_key
    if not ssh_key_content:
        current_app.logger.warning("No ssh_key content in config")
        raise ValueError("ssh_key_content cannot be empty")

    # This import is local to the function to avoid circular dependencies
    # if it were to be used more broadly.
    import tempfile

    temp_key_path = None
    try:
        # Create a named temp file that will be deleted on close.
        # with tempfile.NamedTemporaryFile(
        #   mode='w', delete=False, newline='', suffix='_sshkey', encoding='utf-8'
        # ) as temp_key_file:
        #     temp_key_file.write(ssh_key_content+"\n")
        # ascii encoding already done in backends.py on saving
        # ssh_key_content = ssh_key_content.encode("ascii").decode("ascii")
        ssh_key_content = ssh_key_content.replace("\r\n", "\n").replace("\r", "\n")
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            newline="\n",
            suffix="_sshkey",
            encoding="ascii",
            errors="strict",
        ) as temp_key_file:
            temp_key_file.write(ssh_key_content)
            if not ssh_key_content.endswith("\n"):
                temp_key_file.write("\n")  # Ensure trailing newline if not present
            temp_key_path = temp_key_file.name
            temp_key_path = Path(temp_key_path).as_posix()
            # Change permissions to 600 (owner read/write only)
            # Note: 0o600 is octal notation for permission 600
            os.chmod(temp_key_path, 0o600)
            # config["ssh_key_file"] = temp_key_path
        yield temp_key_path
    finally:
        if temp_key_path and os.path.exists(temp_key_path):
            try:
                os.remove(temp_key_path)
            except OSError as e:
                current_app.logger.error(
                    f"Error removing temp SSH key file '{temp_key_path}': {e}"
                )


def handle_api_error(error: str, status_code: int = 500) -> tuple[Response, int]:
    """
    Returns a JSON error response with a timestamp and status code.
    """
    return jsonify(
        {
            "error_message": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status_code,
        }
    ), status_code
