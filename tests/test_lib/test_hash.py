# File: tests/test_lib/test_hash.py
import pytest

from restikls.lib.hash import better_hash32, simple_hash32


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("", 0),
        ("a", simple_hash32("a")),
        ("abc", simple_hash32("abc")),
        ("user:123", simple_hash32("user:123")),
    ],
)
def test_simple_hash32_deterministic(input_str, expected):
    assert simple_hash32(input_str) == expected
    assert simple_hash32(input_str) == simple_hash32(input_str)  # test determinism
    assert isinstance(simple_hash32(input_str), int)


@pytest.mark.parametrize(
    "input_str",
    [
        "",
        "a",
        "abc",
        "user:123",
        "user:124",
    ],
)
def test_better_hash32_deterministic_and_range(input_str):
    h = better_hash32(input_str)
    assert isinstance(h, int)
    assert 0 <= h <= 0xFFFFFFFF
    assert h == better_hash32(input_str)  # test determinism


def test_hash_variance():
    # Ensure that even minor differences produce different hashes
    assert better_hash32("user:123") != better_hash32("user:124")
    assert simple_hash32("abc") != simple_hash32("abd")


def test_hash_seed_effect():
    # Verify that different seeds change the result
    assert simple_hash32("key", seed=1) != simple_hash32("key", seed=2)
    assert better_hash32("key", seed=1) != better_hash32("key", seed=2)
