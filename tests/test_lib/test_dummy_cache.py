# File: tests/test_lib/test_dummy_cache.py
import pytest

from restikls.lib.dummy_cache import DummyCache


@pytest.fixture
def cache():
    """Create a fresh DummyCache instance for each test."""
    return DummyCache()


def test_get_with_default(cache):
    """Test get method returns the provided default value."""
    result = cache.get("key", default="default_value")
    assert result == "default_value"


def test_get_without_default(cache):
    """Test get method returns None when no default is provided."""
    result = cache.get("key")
    assert result is None


def test_get_with_empty_key(cache):
    """Test get method with an empty key."""
    result = cache.get("", default=42)
    assert result == 42


def test_set_executes_without_error(cache):
    """Test set method executes without raising errors for various inputs."""
    cache.set("key", "value")
    cache.set("key", None, timeout=10)
    cache.set("", [1, 2, 3], timeout=None)
    assert True  # No exceptions raised


def test_set_has_no_effect(cache):
    """Test set method does not affect get or has methods."""
    cache.set("key", "value", timeout=100)
    assert cache.get("key", default="other") == "other"
    assert cache.has("key") is False


def test_has_always_false(cache):
    """Test has method always returns False."""
    cache.set("key", "value")
    assert cache.has("key") is False
    assert cache.has("") is False
    assert cache.has("nonexistent") is False


def test_clear_executes_without_error(cache):
    """Test clear method executes without raising errors."""
    cache.clear()
    assert True  # No exceptions raised


def test_clear_has_no_effect(cache):
    """Test clear method does not affect get or has methods."""
    cache.set("key", "value")
    cache.clear()
    assert cache.get("key", default="default") == "default"
    assert cache.has("key") is False
