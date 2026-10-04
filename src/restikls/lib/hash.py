# File: src/restikls/lib/hash.py
"""
Provides simple and improved 32-bit hash functions for string inputs.
Includes polynomial rolling hash and FNV-inspired hash implementations
for use in caching and general-purpose hashing needs.
"""


def simple_hash32(s: str, seed: int = 0) -> int:
    """
    Computes a simple 32-bit hash of a string using a polynomial rolling method.

    Args:
        s (str): Input string to hash.
        seed (int, optional): Starting seed value. Defaults to 0.

    Returns:
        int: Unsigned 32-bit integer hash value.

    Notes:
        - Fast and deterministic.
        - Moderate collision resistance.
        - Suitable for internal cache keys where hash stability is required.
    """
    h = seed
    for c in s:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return h


def better_hash32(s: str, seed: int = 0) -> int:
    """
    Computes an improved 32-bit hash of a string using FNV-style mixing and bit-level avalanche.

    Args:
        s (str): Input string to hash.
        seed (int, optional): Starting seed value. Defaults to 0.

    Returns:
        int: Unsigned 32-bit integer hash value.

    Notes:
        - Offers better mixing and variance than simple_hash32.
        - Fast, deterministic, and platform-independent.
        - Suitable for cache keys or use cases requiring consistent, high-variance hashes.
    """
    h = seed ^ 0x811C9DC5  # Start with an offset basis (used in FNV)
    for c in s:
        h = (h ^ ord(c)) * 0x01000193  # Mix with FNV prime
        h = h & 0xFFFFFFFF  # Ensure 32-bit
        h ^= h >> 13
        h ^= (h << 7) & 0xFFFFFFFF
        h ^= h >> 17
    return h
