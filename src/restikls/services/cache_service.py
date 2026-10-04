# File: src/restikls/services/cache_service.py
"""
CacheService provides methods for generating cache keys, storing, retrieving,
and clearing cached data, and a decorator for caching function results.
"""

import hashlib
import re
from functools import wraps
from typing import Any, TypeVar, ParamSpec, Protocol


K = TypeVar("K", contravariant=True)
V = TypeVar("V")
class CacheBackend(Protocol[K, V]):
    def get(self, key: K) -> V | None: ...
    def set(self, key: K, value: V, timeout: int | None = None) -> None: ...
    def delete(self, key: K) -> None: ...
    def clear(self) -> None: ...
    def has(self, key: K) -> bool: ...

T = TypeVar("T")
P = ParamSpec("P")

KEY_PATTERN_FOR_DEBUG = re.compile(r'[^a-zA-Z0-9-]+')

class CacheService:
    """
    Service for handling caching operations.
    """
    cache: CacheBackend
    default_ttl: int
    key_prefix: str = ""
    # Suffix appended to key_prefix to build the index key of the namespace.
    INDEX_SUFFIX: str = "_index"
    debug: bool = False

    def __init__(self, cache: CacheBackend, timeout: int | None = 600, key_prefix: str="", debug: bool = False):
        self.cache = cache
        self.default_ttl = timeout or 600  # 10 minutes default TTL
        self.key_prefix = key_prefix
        self.debug = debug
        # Key under which this namespace's keys are tracked, empty when the
        # service has no key prefix and therefore no namespace of its own.
        self.index_key: str = (
            f"{self.key_prefix}{self.INDEX_SUFFIX}" if self.key_prefix else ""
        )

    def generate_key(self, obj: Any) -> str:
        """
        Generate a cache key from an object (e.g., command list).
        """
        # let's put a safety limit on length
        key_str = str(obj)[:5000]
        # pad with key prefix (int)
        if self.key_prefix:
            assert isinstance(self.key_prefix, str)
            key_str = f"{self.key_prefix}_{key_str}"

        if self.debug:
            _hash = hashlib.blake2b(key_str.encode(), digest_size=4).hexdigest()
            key_str = KEY_PATTERN_FOR_DEBUG.sub('_', key_str.replace('--', '-'))
            key_str = f"{key_str}_{_hash}"
        else:
            key_str = hashlib.md5(key_str.encode("utf-8")).hexdigest()
        return key_str

    def has(self, key: str) -> bool:
        """
        Check if a key exists in the cache.
        """
        # return key in self.cache
        return self.cache.has(key)

    def get(self, key:str) -> Any:
        """
        Retrieve a value from the cache.
        """
        return self.cache.get(key)

    def set(self, key: str, value: Any, timeout: int|None=None) -> None:
        """
        Set a value in the cache with an optional TTL.
        """
        ttl: int = timeout or self.default_ttl
        self.cache.set(key, value, timeout=ttl)
        self._track(key, timeout=ttl)

    def _track(self, key: str, timeout: int|None=None) -> None:
        """
        Record a key in this namespace's index so that clear() can later
        delete the entries of this namespace only.
        Does nothing when the service has no key prefix.
        """
        if not self.index_key:
            return
        tracked = self.cache.get(self.index_key) or set()
        tracked.add(key)
        # The index is written after the entry it tracks and shares its TTL, so
        # it never expires before the entries it points at.
        self.cache.set(self.index_key, tracked, timeout=timeout or self.default_ttl)

    def clear(self) -> bool:
        """
        Clear only the entries belonging to this service's namespace.

        Entries of other namespaces (i.e. other repositories) are left
        untouched. A service without a key prefix has no namespace to scope
        the clear to, so it clears nothing.
        """
        if not self.index_key:
            return True
        tracked = self.cache.get(self.index_key) or set()
        for key in tracked:
            self.cache.delete(key)
        self.cache.delete(self.index_key)
        return True

    def stats(self) -> dict[str, Any]:
        """
        Return statistics about the cache, such as the number of entries
        and the TTL of the namespace index.
        """
        keys = self.cache.get(self.index_key) or set()
        total_entries_size = 0
        keys_map = []
        for key in keys:
            record = self.cache.get(key)
            size_of_record = len(str(record)) if record is not None else 0
            size_of_record_in_kbytes = size_of_record
            total_entries_size += size_of_record_in_kbytes
            keys_map.append({"size": size_of_record_in_kbytes, "key": key})
        stats = {
            "num_entries": len(keys),
            "entries": keys_map,
            "entries_size": f"{str(round(total_entries_size / 1024, 2))} KB",
            "index_ttl": self.default_ttl,
        }

        return stats

    # Unused and buggy for args in generate_key
    # def cached(self, timeout: Optional[int] = None) -> Callable[[Callable[P, T]], Callable[P, Optional[T]]]:
    #     """
    #     Decorator to cache function results.
    #     """
    #     def decorator(f: Callable[P, T]) -> Callable[P, Optional[T]]:
    #         @wraps(f)
    #         def decorated_function(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
    #             func_name = getattr(f, "__name__", type(f).__name__)
    #             cache_key = self.generate_key(
    #                 (func_name, args, tuple(sorted(kwargs.items())))
    #             )
    #             if self.has(cache_key):
    #                 return self.get(cache_key)
    #             result = f(*args, **kwargs)
    #             self.set(cache_key, result, timeout=timeout)
    #             return result
    #         return decorated_function
    #     return decorator
