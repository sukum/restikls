# File: tests/test_lib/test_filters.py

from datetime import datetime, timedelta, timezone

from restikls.lib.filters import (
    assign_color_filter,
    format_datetime_filter,
    parse_datetime,
)


def test_parse_datetime_various_formats():
    """Test that parse_datetime handles various ISO 8601 formats correctly."""
    # With Z (Zulu/UTC)
    dt_zulu_str = "2023-10-27T10:00:00Z"
    assert parse_datetime(dt_zulu_str) == datetime(
        2023, 10, 27, 10, 0, 0, tzinfo=timezone.utc
    )

    # With fractional seconds
    dt_frac_str = "2023-10-27T10:00:00.123456Z"
    assert parse_datetime(dt_frac_str) == datetime(
        2023, 10, 27, 10, 0, 0, 123456, tzinfo=timezone.utc
    )

    # With long fractional seconds (should be truncated)
    dt_long_frac_str = "2023-10-27T10:00:00.123456789Z"
    assert parse_datetime(dt_long_frac_str) == datetime(
        2023, 10, 27, 10, 0, 0, 123456, tzinfo=timezone.utc
    )

    # With timezone offset
    dt_offset_str = "2023-10-27T12:00:00+02:00"
    tz = timezone(timedelta(hours=2))
    assert parse_datetime(dt_offset_str) == datetime(2023, 10, 27, 12, 0, 0, tzinfo=tz)


def test_format_datetime_filter(app):
    """Test the datetime formatting filter."""
    with app.app_context():
        # Test default format (no seconds)
        iso_string = "2023-10-27T10:30:59.123Z"
        assert format_datetime_filter(iso_string) == "2023-10-27 10:30"

        # Test with seconds
        assert (
            format_datetime_filter(iso_string, show_seconds=True)
            == "2023-10-27 10:30:59"
        )

        # Test invalid input
        assert format_datetime_filter("not a date") == "not a date"


def test_assign_color_filter():
    """Test the color assignment filter for consistency."""
    color1 = assign_color_filter("my-hostname")
    color2 = assign_color_filter("my-hostname")
    color3 = assign_color_filter("another-hostname")

    # Same input should always produce the same color
    assert color1 == color2

    # Different input may or may not be different, but should be a valid color
    from restikls.lib.filters import COLORS

    assert color1 in COLORS
    assert color3 in COLORS
