import pytest

from laptop_market_scraper.normalization import (
    normalize_count,
    normalize_idr,
    normalize_percent,
    normalize_rating,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("15", 15),
        ("100+ terjual", 100),
        ("1rb+ terjual", 1000),
        ("1,2rb+ terjual", 1200),
        ("2.5k", 2500),
        ("1jt+", 1_000_000),
        ("-", None),
        ("", None),
        (None, None),
        (50, 50),
        ("1.5m", 1_500_000),
        ("habis", None),
    ],
)
def test_normalize_count(raw, expected):
    assert normalize_count(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Rp12.499.000", 12_499_000),
        ("Rp 1.500.000,00", 1_500_000),
        ("1500000", 1_500_000),
        (12_499_000, 12_499_000),
        ("-", None),
        ("", None),
        (None, None),
        ("Gratis", None),
    ],
)
def test_normalize_idr(raw, expected):
    assert normalize_idr(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("15%", 15.0),
        ("15.5%", 15.5),
        ("15,5%", 15.5),
        (20, 20.0),
        (20.5, 20.5),
        ("-", None),
        ("", None),
        (None, None),
        ("n/a", None),
    ],
)
def test_normalize_percent(raw, expected):
    assert normalize_percent(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("4,9", 4.9),
        ("4.9", 4.9),
        ("5", 5.0),
        ("4.8 / 5", 4.8),
        (4.5, 4.5),
        ("-", None),
        ("", None),
        (None, None),
        ("none", None),
    ],
)
def test_normalize_rating(raw, expected):
    assert normalize_rating(raw) == expected
