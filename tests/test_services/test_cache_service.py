# File: tests/test_services/test_cache_service.py
import hashlib
from typing import Any
from unittest.mock import Mock

import pytest

from restikls.services.cache_service import CacheService
from restikls.defaults import DefaultConfig


class FakeCache:
    """Minimal in-memory cache backend, sufficient to exercise namespaces."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.timeouts: dict[str, int | None] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.store.get(key, default)

    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        self.store[key] = value
        self.timeouts[key] = timeout

    def has(self, key: str) -> bool:
        return key in self.store

    def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.timeouts.pop(key, None)

    def clear(self) -> None:
        self.store.clear()
        self.timeouts.clear()


@pytest.fixture
def mock_cache():
    """Create a mock cache with get, set, has, and clear methods."""
    cache = Mock()
    cache.get.return_value = None
    cache.has.return_value = False
    return cache


@pytest.fixture
def cache_service(mock_cache):
    """Create a CacheService instance with a mock cache and default TTL of 600."""
    return CacheService(mock_cache, timeout=600)


@pytest.fixture
def memory_cache() -> FakeCache:
    """Create an in-memory cache backend shared by several services."""
    return FakeCache()


@pytest.fixture
def namespaced_service(memory_cache: FakeCache) -> CacheService:
    """Create a CacheService with a repo derived key prefix."""
    return CacheService(memory_cache, timeout=600, key_prefix="abc12345")


def test_init_with_default_timeout(mock_cache):
    """Test initialization with default TTL."""
    service = CacheService(mock_cache)
    assert service.cache == mock_cache
    assert service.default_ttl is DefaultConfig.CACHE_DEFAULT_TIMEOUT


def test_init_with_custom_timeout(mock_cache):
    """Test initialization with custom TTL."""
    service = CacheService(mock_cache, timeout=300)
    assert service.default_ttl == 300


def test_init_with_zero_timeout(mock_cache):
    """Test initialization with TTL of 0 sets default_ttl to the default value."""
    service = CacheService(mock_cache, timeout=0)
    assert service.default_ttl is DefaultConfig.CACHE_DEFAULT_TIMEOUT


def test_init_with_none_timeout(mock_cache):
    """Test initialization with TTL of None sets default_ttl to the default value."""
    service = CacheService(mock_cache, timeout=None)
    assert service.default_ttl is DefaultConfig.CACHE_DEFAULT_TIMEOUT


def test_generate_key_consistent(cache_service):
    """Test generate_key produces consistent MD5 hash for same input."""
    obj = ["command", 123]
    expected_key = hashlib.md5(str(obj).encode("utf-8")).hexdigest()
    assert cache_service.generate_key(obj) == expected_key
    assert cache_service.generate_key(obj) == cache_service.generate_key(obj)


def test_generate_key_different_inputs(cache_service):
    """Test generate_key produces different hashes for different inputs."""
    key1 = cache_service.generate_key("input1")
    key2 = cache_service.generate_key("input2")
    assert key1 != key2


def test_generate_key_edge_cases(cache_service):
    """Test generate_key with edge case inputs."""
    assert len(cache_service.generate_key("")) == 32  # MD5 hash length
    assert len(cache_service.generate_key(None)) == 32
    assert cache_service.generate_key(None) == cache_service.generate_key(None)


def test_has_calls_cache_has(cache_service, mock_cache):
    """Test has method calls cache.has with correct key."""
    cache_service.has("test_key")
    mock_cache.has.assert_called_once_with("test_key")


def test_has_returns_cache_result(cache_service, mock_cache):
    """Test has method returns cache.has result."""
    mock_cache.has.return_value = True
    assert cache_service.has("test_key") is True
    mock_cache.has.return_value = False
    assert cache_service.has("test_key") is False


def test_get_calls_cache_get(cache_service, mock_cache):
    """Test get method calls cache.get with correct key."""
    cache_service.get("test_key")
    mock_cache.get.assert_called_once_with("test_key")


def test_get_returns_cache_result(cache_service, mock_cache):
    """Test get method returns cache.get result."""
    mock_cache.get.return_value = "cached_value"
    assert cache_service.get("test_key") == "cached_value"


def test_set_with_default_timeout(cache_service, mock_cache):
    """Test set method uses default TTL when none provided."""
    cache_service.set("test_key", "value")
    mock_cache.set.assert_called_once_with("test_key", "value", timeout=600)


def test_set_with_custom_ttl(cache_service, mock_cache):
    """Test set method uses provided TTL."""
    cache_service.set("test_key", "value", timeout=300)
    mock_cache.set.assert_called_once_with("test_key", "value", timeout=300)


def test_set_with_none_timeout(cache_service, mock_cache):
    """Test set method omits timeout when TTL is None."""
    cache_service.default_ttl = None
    cache_service.set("test_key", "value", timeout=None)
    mock_cache.set.assert_called_once_with("test_key", "value", timeout=None)


def test_set_with_zero_timeout(cache_service, mock_cache):
    """Test set method uses default TTL when TTL is 0."""
    cache_service.set("test_key", "value", timeout=0)
    mock_cache.set.assert_called_once_with("test_key", "value", timeout=600)


def test_clear_without_prefix_does_not_clear_shared_cache(cache_service, mock_cache) -> None:
    """Test clear is a no-op when there is no namespace to scope it to."""
    result = cache_service.clear()

    assert result is True
    mock_cache.clear.assert_not_called()


def test_init_builds_index_key_from_prefix(mock_cache) -> None:
    """Test the namespace index key derives from the key prefix."""
    service = CacheService(mock_cache, timeout=600, key_prefix="abc12345")

    assert service.index_key == "abc12345_index"


def test_init_without_prefix_has_no_index_key(mock_cache) -> None:
    """Test a service without key prefix has no namespace index key."""
    service = CacheService(mock_cache, timeout=600)

    assert service.index_key == ""


def test_set_tracks_key_in_namespace_index(namespaced_service, memory_cache) -> None:
    """Test set records the stored key in the namespace index."""
    # Arrange
    key = namespaced_service.generate_key(["restic", "snapshots"])

    # Act
    namespaced_service.set(key, ["snapshot"])

    # Assert
    assert memory_cache.get("abc12345_index") == {key}
    assert memory_cache.get(key) == ["snapshot"]


def test_set_writes_index_with_service_ttl(namespaced_service, memory_cache) -> None:
    """Test the namespace index shares the TTL of the entries it tracks."""
    # Act
    namespaced_service.set("test_key", "value")

    # Assert
    assert memory_cache.timeouts["abc12345_index"] == 600


def test_set_without_prefix_writes_no_index(memory_cache) -> None:
    """Test set does not create an index when the service has no prefix."""
    # Arrange
    service = CacheService(memory_cache, timeout=600)

    # Act
    service.set("test_key", "value")

    # Assert
    assert memory_cache.store == {"test_key": "value"}


def test_clear_removes_only_own_namespace_entries(memory_cache) -> None:
    """Test clear leaves the entries of other namespaces untouched."""
    # Arrange
    own_service = CacheService(memory_cache, timeout=600, key_prefix="own00000")
    other_service = CacheService(memory_cache, timeout=600, key_prefix="other111")
    own_key = own_service.generate_key(["snapshots"])
    other_key = other_service.generate_key(["snapshots"])
    own_service.set(own_key, "own")
    other_service.set(other_key, "other")

    # Act
    result = own_service.clear()

    # Assert
    assert result is True
    assert memory_cache.has(own_key) is False
    assert memory_cache.has(other_key) is True
    assert memory_cache.get(other_key) == "other"


def test_clear_removes_own_namespace_index(namespaced_service, memory_cache) -> None:
    """Test clear drops the namespace index itself."""
    # Arrange
    namespaced_service.set("test_key", "value")

    # Act
    namespaced_service.clear()

    # Assert
    assert memory_cache.has("abc12345_index") is False


@pytest.mark.parametrize("entry_count", [1, 3, 5])
def test_clear_removes_every_tracked_entry(memory_cache, entry_count: int) -> None:
    """Test clear removes all entries tracked for the namespace."""
    # Arrange
    service = CacheService(memory_cache, timeout=600, key_prefix="abc12345")
    keys = [service.generate_key(["cmd", index]) for index in range(entry_count)]
    for key in keys:
        service.set(key, "value")

    # Act
    service.clear()

    # Assert
    assert [key for key in keys if memory_cache.has(key)] == []
    assert memory_cache.store == {}


def test_clear_on_empty_namespace_succeeds(memory_cache) -> None:
    """Test clear succeeds when nothing was ever cached."""
    # Arrange
    service = CacheService(memory_cache, timeout=600, key_prefix="abc12345")

    # Act
    result = service.clear()

    # Assert
    assert result is True
    assert memory_cache.store == {}
