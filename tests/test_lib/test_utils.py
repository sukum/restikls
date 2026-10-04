# File: tests/test_lib/test_utils.py

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import current_app

from restikls.lib.utils import (
    combine_json_lines,
    manage_ssh_key_file,
    slice_paged_data,
    time_process,
)


# @pytest.fixture
# def mock_flask_g():
#     """Fixture to mock Flask's g object with config"""

#     class MockG:
#         def __init__(self):
#             self.repo_cred = 

#     return MockG()

@pytest.fixture
def mock_logger():
    """Fixture to provide a mock logger."""
    return MagicMock()


@pytest.fixture
def mock_tempfile():
    """Fixture to mock tempfile.NamedTemporaryFile."""
    with patch("tempfile.NamedTemporaryFile") as mock_file:
        mock_file.return_value.__enter__.return_value.name = "/tmp/test_sshkey"
        mock_file.return_value.__enter__.return_value.write = MagicMock()
        yield mock_file


@pytest.fixture
def mock_os():
    """Fixture to mock os module functions."""
    with (
        patch("os.chmod") as mock_chmod,
        patch("os.remove") as mock_remove,
        patch("os.path.exists") as mock_exists,
    ):
        mock_exists.return_value = True
        yield {"chmod": mock_chmod, "remove": mock_remove, "exists": mock_exists}


@pytest.fixture
def mock_current_app(app):
    """Fixture to mock Flask's current_app."""
    with patch("restikls.lib.utils.current_app") as mock_app:
        mock_app.logger = MagicMock()
        yield mock_app


def test_combine_json_lines_valid():
    """Test combining valid newline-separated JSON objects."""
    json_string = '{"key1": "value1"}\n{"key2": "value2"}'
    expected_output = json.dumps([{"key1": "value1"}, {"key2": "value2"}], indent=2)
    assert combine_json_lines(json_string) == expected_output


def test_combine_json_lines_single_line():
    """Test with a single JSON object."""
    json_string = '{"key": "value"}'
    expected_output = json.dumps([{"key": "value"}], indent=2)
    assert combine_json_lines(json_string) == expected_output


def test_combine_json_lines_empty_string():
    """Test with an empty input string."""
    assert combine_json_lines("") == "[]"


def test_combine_json_lines_with_blank_lines():
    """Test with blank lines interspersed."""
    json_string = '\n{"a": 1}\n\n{"b": 2}\n'
    expected_output = json.dumps([{"a": 1}, {"b": 2}], indent=2)
    assert combine_json_lines(json_string) == expected_output


def test_combine_json_lines_invalid_json(app):
    """Test that it raises ValueError for malformed JSON."""
    json_string = '{"key": "value"}\nthis is not json'
    with pytest.raises(ValueError):
        combine_json_lines(json_string)


def test_decorator_logs_when_slow(app, monkeypatch):
    """Test that warning is logged when execution exceeds threshold"""
    with app.app_context():
        with monkeypatch.context() as m:
            mock_logger = MagicMock()
            m.setattr(current_app, "logger", mock_logger)
            with patch("time.time", side_effect=[0, 5]):  # 11 sec execution

                @time_process(threshold=4)
                def slow_func():
                    return "done"

                result = slow_func()

            assert result == "done"
            mock_logger.warning.assert_called_once()
            assert "exceeded 4 sec threshold" in mock_logger.warning.call_args[0][0]


def test_decorator_no_log_when_fast(app, monkeypatch):
    """Test no warning is logged when execution is under threshold"""
    with app.app_context():
        with monkeypatch.context() as m:
            mock_logger = MagicMock()
            m.setattr(current_app, "logger", mock_logger)
            with patch("time.time", side_effect=[0, 2]):  # 5 sec execution

                @time_process(threshold=3)
                def fast_func():
                    return "quick"

                result = fast_func()

            assert result == "quick"
            mock_logger.warning.assert_not_called()


def test_decorator_preserves_function_metadata(app, monkeypatch):
    """Test that function metadata (name, docstring) is preserved"""
    with patch("time.time", return_value=0):

        @time_process()
        def sample_func():
            """Test docstring"""
            pass

    assert sample_func.__name__ == "sample_func"
    assert sample_func.__doc__ == "Test docstring"


def test_pagination_info(app):
    """Test the pagination info calculator."""
    app.config["PAGE_RECORDS"] = 20
    from restikls.lib.utils import pagination_info

    # mock_g.config = MagicMock()
    # mock_g.config.__getitem__.return_value = 20  # Return 20 for any key access

    # Test case 1: Full pages
    data_1 = list(range(100))
    records_per_page, record_count, total_pages = pagination_info(data_1)
    assert records_per_page == 20
    assert record_count == 100
    assert total_pages == 5

    # Test case 2: Partial last page
    data_2 = list(range(95))
    _, _, total_pages = pagination_info(data_2)
    assert total_pages == 5

    # Test case 3: Less than one page
    data_3 = list(range(10))
    _, _, total_pages = pagination_info(data_3)
    assert total_pages == 1

    # Test case 4: Empty data
    data_4 = []
    _, record_count, total_pages = pagination_info(data_4)
    assert record_count == 0
    assert total_pages == 0

    # Test case 5: Exactly one page
    data_5 = list(range(20))
    _, _, total_pages = pagination_info(data_5)
    assert total_pages == 1

    app.config["PAGE_RECORDS"] = 3
    # 7 pages
    data_5 = list(range(20))
    _, _, total_pages = pagination_info(data_5)
    assert total_pages == 7

    app.config["PAGE_RECORDS"] = 10
    # 2 pages
    data_5 = list(range(20))
    _, _, total_pages = pagination_info(data_5)
    assert total_pages == 2


def test_handle_api_error(app):
    """Test the API error handler creates a valid JSON response."""
    from restikls.lib.utils import handle_api_error

    with app.app_context():
        response, status_code = handle_api_error("Test error message", 404)

        assert status_code == 404

        # The response is a JSON string, so we need to parse it
        data = json.loads(response.get_data(as_text=True))
        # print(data)
        assert data["status"] == 404
        assert data["error_message"] == "Test error message"
        assert "timestamp" in data


# ------- slice_paged_data -------------


def test_slice_paged_data_basic(app, monkeypatch):
    """Test basic pagination functionality"""
    with app.app_context():
        app.config["PAGE_RECORDS"] = 3
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        def list_slice_paged_data(data, page):
            return list(slice_paged_data(data, page))

        # Test first page
        assert list_slice_paged_data(data, 1) == [1, 2, 3]

        # Test second page
        assert list_slice_paged_data(data, 2) == [4, 5, 6]

        # Test third page
        assert list_slice_paged_data(data, 3) == [7, 8, 9]

        # Test fourth page (partial)
        assert list_slice_paged_data(data, 4) == [10]


def test_slice_paged_data_empty_input(app, monkeypatch):
    """Test with empty input list"""
    with app.app_context():
        app.config["PAGE_RECORDS"] = 3
        assert list(slice_paged_data([], 1)) == []
        assert list(slice_paged_data([], 2)) == []


def test_slice_paged_data_out_of_range_page(app, monkeypatch):
    """Test with page number that's out of range"""
    with app.app_context():
        app.config["PAGE_RECORDS"] = 3
        data = [1, 2, 3, 4, 5]

        # Page beyond available data
        assert list(slice_paged_data(data, 3)) == []  # Only 2 pages exist

        # Page 0 (should behave same as page 1)
        assert list(slice_paged_data(data, 0)) == [1, 2, 3]

        # Negative page (should behave same as page 1)
        assert list(slice_paged_data(data, -1)) == [1, 2, 3]


def test_slice_paged_data_default_page(app, monkeypatch):
    """Test that default page is 1"""
    with app.app_context():
        app.config["PAGE_RECORDS"] = 3
        data = [1, 2, 3, 4, 5]
        assert list(slice_paged_data(data)) == [1, 2, 3]


def test_slice_paged_data_different_page_sizes(app):
    """Test with different PAGE_RECORDS configurations"""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    with app.app_context():

        # Test with page size 1
        # mock_g = type("MockG", (), {"config": {"PAGE_RECORDS": 1}})()
        # with patch("restikls.lib.utils.g", mock_g):
        app.config["PAGE_RECORDS"] = 1
        assert list(slice_paged_data(data, 1)) == [1]
        assert list(slice_paged_data(data, 2)) == [2]

        # Test with page size 5
        # mock_g = type("MockG", (), {"config": {"PAGE_RECORDS": 5}})()
        # with patch("restikls.lib.utils.g", mock_g):
        app.config["PAGE_RECORDS"] = 5
        assert list(slice_paged_data(data, 1)) == [1, 2, 3, 4, 5]
        assert list(slice_paged_data(data, 2)) == [6, 7, 8, 9, 10]

        # Test with page size larger than data
        # mock_g = type("MockG", (), {"config": {"PAGE_RECORDS": 20}})()
        # with patch("restikls.lib.utils.g", mock_g):
        app.config["PAGE_RECORDS"] = 20
        assert list(slice_paged_data(data, 1)) == data
        assert list(slice_paged_data(data, 2)) == []


# --------- manage_ssh_key_file ------------


def test_manage_ssh_key_file_with_valid_key(
    mock_tempfile, mock_os, mock_current_app, sftp_config
):
    """Test context manager with a valid SSH key in config."""
    sftp_config.ssh_key = "ssh-rsa AAAAB3NzaC1yc2E..."
    with manage_ssh_key_file(sftp_config) as key_path:
        assert key_path == "/tmp/test_sshkey"
        # assert sftp_config.ssh_key_file == "/tmp/test_sshkey"
        mock_tempfile.return_value.__enter__.return_value.write.assert_any_call(
            "ssh-rsa AAAAB3NzaC1yc2E..."
        )
        mock_tempfile.return_value.__enter__.return_value.write.assert_any_call("\n")
        mock_os["chmod"].assert_called_with("/tmp/test_sshkey", 0o600)
    assert not hasattr(sftp_config, "ssh_key_file")
    mock_os["remove"].assert_called_with("/tmp/test_sshkey")


def test_manage_ssh_key_file_with_ssh_key_content(
    sftp_config, mock_tempfile, mock_os, mock_current_app
):
    """Test context manager with direct ssh_key_content."""
    ssh_key = "ssh-rsa BBBBB3NzaC1yc2E..."
    with manage_ssh_key_file(sftp_config, ssh_key_content=ssh_key) as key_path:
        assert key_path == "/tmp/test_sshkey"
        # assert sftp_config.ssh_key_file == "/tmp/test_sshkey"
        mock_tempfile.return_value.__enter__.return_value.write.assert_any_call(
            "ssh-rsa BBBBB3NzaC1yc2E..."
        )
        mock_tempfile.return_value.__enter__.return_value.write.assert_any_call("\n")
        mock_os["chmod"].assert_called_with("/tmp/test_sshkey", 0o600)
    assert not hasattr(sftp_config, "ssh_key_file")
    mock_os["remove"].assert_called_with("/tmp/test_sshkey")


def test_manage_ssh_key_file_no_key(
    local_config, mock_tempfile, mock_os, mock_current_app
):
    """Test context manager when no SSH key is provided."""
    with (
        pytest.raises(ValueError),
        manage_ssh_key_file(local_config) as _
    ):
        pass
        # assert _ is None
        # assert "ssh_key_file" not in local_config
        # mock_tempfile.assert_not_called()
        # mock_os["chmod"].assert_not_called()
        # mock_os["remove"].assert_not_called()


def test_manage_ssh_key_file_empty_key_content(
    local_config, mock_tempfile, mock_os, mock_current_app
):
    """Test context manager with empty ssh_key_content."""
    with (
        pytest.raises(ValueError),
        manage_ssh_key_file(local_config, ssh_key_content="") as _
    ):
        pass
        # assert _ is None
        # assert "ssh_key_file" not in local_config
        # mock_tempfile.assert_not_called()
        # mock_os["chmod"].assert_not_called()
        # mock_os["remove"].assert_not_called()


def test_manage_ssh_key_file_newline_normalization(
    sftp_config, mock_tempfile, mock_os, mock_current_app
):
    """Test newline normalization (\r\n and \r to \n)."""
    ssh_key = "ssh-rsa AAAAB3NzaC1yc2E...\r\n"
    with manage_ssh_key_file(sftp_config, ssh_key_content=ssh_key) as key_path:
        assert key_path == "/tmp/test_sshkey"
        mock_tempfile.return_value.__enter__.return_value.write.assert_called_with(
            "ssh-rsa AAAAB3NzaC1yc2E...\n"
        )
        mock_os["chmod"].assert_called_with("/tmp/test_sshkey", 0o600)
    mock_os["remove"].assert_called_with("/tmp/test_sshkey")


def test_manage_ssh_key_file_no_trailing_newline(
    sftp_config, mock_tempfile, mock_os, mock_current_app
):
    """Test adding trailing newline if missing."""
    ssh_key = "ssh-rsa AAAAB3NzaC1yc2E..."
    with manage_ssh_key_file(sftp_config, ssh_key_content=ssh_key) as key_path:
        assert key_path == "/tmp/test_sshkey"
        mock_tempfile.return_value.__enter__.return_value.write.assert_any_call(
            "ssh-rsa AAAAB3NzaC1yc2E..."
        )
        mock_tempfile.return_value.__enter__.return_value.write.assert_any_call("\n")
        mock_os["chmod"].assert_called_with("/tmp/test_sshkey", 0o600)
    mock_os["remove"].assert_called_with("/tmp/test_sshkey")


def test_manage_ssh_key_file_non_ascii_content(
    sftp_config, mock_tempfile, mock_os, mock_current_app
):
    pytest.skip('Skipping test as SSH key is encode("ascii", "ignore") in config_route save')
    """Test handling of non-ASCII SSH key content."""
    ssh_key = "ssh-rsa AAAAB3NzaC1yc2E...🔑"
    with pytest.raises(UnicodeEncodeError):
        with manage_ssh_key_file(sftp_config, ssh_key_content=ssh_key):
            pass
    mock_tempfile.assert_not_called()
    mock_os["chmod"].assert_not_called()
    mock_os["remove"].assert_not_called()
