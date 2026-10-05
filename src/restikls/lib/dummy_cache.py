# File: src/restikls/lib/dummy_cache.py

from typing import Any


class DummyCache:
    def get(self, key: str, default: Any=None) -> Any:
        return default

    def set(self, key: str, value: Any, timeout: int | None=None) -> None:
        pass

    def has(self, key: str) -> bool:
        return False

    def delete(self, key: str) -> None:
        pass

    def clear(self) -> None:
        pass
