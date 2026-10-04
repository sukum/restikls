# File: src/restikls/lib/filters.py

"""
Custom Jinja2 filters for the Flask application.
"""

import re
from datetime import datetime
from functools import lru_cache
from typing import Any
from zlib import adler32

from flask import Flask, current_app

# --- Constants ---
FULL_DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DEFAULT_DATETIME_FORMAT: str = "%Y-%m-%d %H:%M"
COLORS: list = ["red", "yellow", "green", "blue", "purple", "pink", "indigo"]
COLORS_COUNT: int = len(COLORS)

# Pre-compiled regex for ISO 8601 datetime strings.
EXPECTED_DATETIME_REGEX: re.Pattern = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"  # Group 1: Main datetime
    r"(\.\d{1,9})?"  # Group 2: Optional fractional seconds
    r"([+-]\d{2}:\d{2}|Z)?$"  # Group 3: Optional timezone
)


def format_datetime_filter(datetime_str: str, show_seconds: bool = False) -> str:
    """
    Jinja filter to format an ISO 8601 datetime string into a more readable form.
    Args:
        datetime_str (str): The datetime string to format (e.g., "2025-06-01T19:17:13Z").
        show_seconds (bool, optional): If True, include seconds in the output.
                                       Defaults to False.
    Returns:
        str: The formatted datetime string, or the original string if parsing fails.
    """
    if not isinstance(datetime_str, str) or len(datetime_str) < 19:
        current_app.logger.warning(
            "Received unexpected datetime format: %s", datetime_str
        )
        return datetime_str
    # .fromisoformat(datetime_str)
    # .strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    try:
        dt_obj = parse_datetime(datetime_str)
        target_format = (
            FULL_DATETIME_FORMAT if show_seconds else DEFAULT_DATETIME_FORMAT
        )
        return dt_obj.strftime(target_format)
    except ValueError:
        # Log the error and return the original string to avoid crashing the template.
        current_app.logger.error(f"Could not parse datetime string: {datetime_str}")
        return datetime_str


@lru_cache(maxsize=256)
def assign_color_filter(value: Any) -> str:
    """
    Jinja filter to consistently assign a color from a predefined list
    based on the input value's hash.
    This is useful for color-coding items like tags or hostnames.
    Args:
        value (any): The value to be hashed for color assignment.
                     It will be converted to a string.
    Returns:
        str: A color name (e.g., "red", "blue").
    """
    # Use zlib.adler32 for a fast, simple hashing algorithm.
    # The result is deterministic, so the same input always gets the same color.
    value_bytes = str(value).encode("utf-8")
    color_index = adler32(value_bytes) % COLORS_COUNT
    return COLORS[color_index]


def parse_datetime(datetime_str: str) -> datetime:
    """
    Parses a wide range of ISO 8601 formatted datetime strings into datetime objects.
    This function is robust and handles varying fractional second precision and
    timezone information.
    Args:
        datetime_str (str): The ISO 8601 datetime string.
    Returns:
        datetime: A timezone-aware datetime object.
    Raises:
        ValueError: If the datetime string format is invalid.
    """
    # Regex to split into parts: main, fractional seconds, and timezone
    match = EXPECTED_DATETIME_REGEX.match(datetime_str)
    if not match:
        raise ValueError(f"Invalid datetime format: {datetime_str}")

    main_part, fractional_part, tz_part = match.groups()

    # ".161727557" or None → ".0"
    # Remove leading "."
    fractional_seconds = (fractional_part or ".0")[1:]
    # Normalize fractional seconds to 6 digits (microseconds) for strptime.
    # Pad to 6 digits
    truncated_fraction = fractional_seconds[:6].ljust(6, "0")

    # Rebuild the string with normalized parts for strptime.
    rebuilt_str = f"{main_part}.{truncated_fraction}"

    # Handle timezone: 'Z' (Zulu/UTC) or offset (e.g., -07:00).
    # "-07:00", "Z", or None → "Z"
    # Parse (note: %z handles ±HH:MM, and "Z" must be replaced with +00:00 for strptime)
    if tz_part == "Z" or not tz_part:
        rebuilt_str += "+00:00"
    else:
        rebuilt_str += tz_part

    return datetime.strptime(rebuilt_str, "%Y-%m-%dT%H:%M:%S.%f%z")


def format_filemode_filter(mode: str | int) -> str:
    """
    Format a file permission mode into a compact octal representation.

    Converts a file mode (either as integer or string) to a shortened octal string
    representation, handling special cases like sticky bits. The output follows
    Unix-style permission formatting conventions.
    The restic command returns it as int, we will keep the case of string open as well.

    Args:
        mode: The file mode, which can be either:
              - An integer (like from os.stat().st_mode)
              - A string representation of the mode

    Returns:
        A formatted octal permission string (e.g., '755', '1777', '2755')

    Examples:
        >>> format_filemode_filter(0o100644)
        '644'
        >>> format_filemode_filter(0o41755)
        '1755'
        >>> format_filemode_filter('0100664')
        '664'
    """
    # Convert the mode to octal string and strip leading zeros
    mode_str = ("%o" % (int(mode, 8) if isinstance(mode, str) else mode)).lstrip("0")

    # Special handling for certain modes (like sticky bits)
    if (mode_str.startswith(("1", "2", "4"))) and len(mode_str) > 4:
        mode_str = mode_str[0] + mode_str[-3:]

    return mode_str


def register_filters(app: Flask) -> None:
    """
    Registers all custom filters with the Flask application.

    Args:
        app (Flask): The Flask application instance.
    """
    app.template_filter("format_datetime")(format_datetime_filter)
    app.template_filter("assign_color")(assign_color_filter)
    app.template_filter("format_filemode")(format_filemode_filter)
