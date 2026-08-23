import numpy as np
import pandas as pd
import pytest

from laptop_market_scraper.audit import NumericFeatureStats, calculate_numeric_stats


def test_calculate_numeric_stats_basic():
    data = [1.0, 2.0, None, 10.0]
    stats = calculate_numeric_stats(data)

    assert isinstance(stats, NumericFeatureStats)
    assert stats.row_count == 4
    assert stats.non_null_count == 3
    assert stats.missing_count == 1
    assert stats.invalid_type_count == 0
    assert stats.coverage_percent == 75.0
    assert stats.missingness_percent == 25.0
    assert stats.minimum == 1.0
    assert stats.median == 2.0
    assert stats.maximum == 10.0
    assert stats.unique_count == 3
    assert stats.zero_count == 0
    assert stats.zero_rate_percent == 0.0


def test_calculate_numeric_stats_empty():
    stats = calculate_numeric_stats([])

    assert stats.row_count == 0
    assert stats.non_null_count == 0
    assert stats.missing_count == 0
    assert stats.invalid_type_count == 0
    assert stats.coverage_percent == 0.0
    assert stats.missingness_percent == 100.0
    assert stats.minimum is None
    assert stats.q1 is None
    assert stats.median is None
    assert stats.q3 is None
    assert stats.maximum is None
    assert stats.unique_count == 0
    assert stats.zero_count == 0
    assert stats.zero_rate_percent == 0.0
    assert stats.skewness is None


def test_calculate_numeric_stats_invalid_types():
    data = ["abc", 10, None, True]
    stats = calculate_numeric_stats(data)

    assert stats.row_count == 4
    assert stats.non_null_count == 1
    assert stats.missing_count == 1
    assert stats.invalid_type_count == 2
    assert stats.coverage_percent == 25.0
    assert stats.missingness_percent == 75.0


def test_calculate_numeric_stats_zeros():
    data = [0.0, 0, 5.0, 0.0]
    stats = calculate_numeric_stats(data)

    assert stats.row_count == 4
    assert stats.non_null_count == 4
    assert stats.zero_count == 3
    assert stats.zero_rate_percent == 75.0


def test_calculate_numeric_stats_skewness():
    # Symmetric distribution
    stats_sym = calculate_numeric_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert stats_sym.skewness is not None
    assert pytest.approx(stats_sym.skewness, abs=1e-5) == 0.0

    # Right-skewed distribution
    stats_skewed = calculate_numeric_stats([1.0, 1.0, 1.0, 2.0, 10.0])
    assert stats_skewed.skewness is not None
    assert stats_skewed.skewness > 0.0

    # Constant distribution (variance == 0)
    stats_const = calculate_numeric_stats([5.0, 5.0, 5.0])
    assert stats_const.skewness is None

    # Insufficient data (< 3 points)
    stats_small = calculate_numeric_stats([1.0, 2.0])
    assert stats_small.skewness is None


def test_calculate_numeric_stats_percentiles():
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    stats = calculate_numeric_stats(data)

    assert stats.minimum == 1.0
    assert stats.q1 == 2.0
    assert stats.median == 3.0
    assert stats.q3 == 4.0
    assert stats.maximum == 5.0


def test_calculate_numeric_stats_pandas_series():
    series = pd.Series([10.0, 20.0, np.nan, 30.0], name="price")
    stats = calculate_numeric_stats(series, expected_dtype="float")

    assert stats.row_count == 4
    assert stats.non_null_count == 3
    assert stats.missing_count == 1
    assert "float" in stats.observed_dtype
