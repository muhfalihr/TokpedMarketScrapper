import math
from typing import Any, Iterable

import numpy as np
import pandas as pd
from pydantic import BaseModel


class NumericFeatureStats(BaseModel):
    row_count: int
    non_null_count: int
    missing_count: int
    coverage_percent: float
    missingness_percent: float
    observed_dtype: str
    invalid_type_count: int
    minimum: float | None
    q1: float | None
    median: float | None
    q3: float | None
    maximum: float | None
    unique_count: int
    zero_count: int
    zero_rate_percent: float
    skewness: float | None


def calculate_numeric_stats(
    series: pd.Series | Iterable[Any], expected_dtype: str = "float"
) -> NumericFeatureStats:
    """Calculate reproducible numeric feature statistics for pandas Series or sequence."""
    if isinstance(series, pd.Series):
        observed_dtype = str(series.dtype)
        items = series.tolist()
    else:
        items = list(series) if not isinstance(series, list) else series
        if len(items) > 0:
            try:
                observed_dtype = str(pd.Series(items).dtype)
            except Exception:
                observed_dtype = expected_dtype
        else:
            observed_dtype = expected_dtype

    row_count = len(items)
    missing_count = 0
    invalid_type_count = 0
    valid_values: list[float] = []

    for item in items:
        if item is None or pd.isna(item):
            missing_count += 1
        elif isinstance(item, bool):
            invalid_type_count += 1
        elif isinstance(item, (int, float, np.number)):
            val = float(item)
            if math.isnan(val):
                missing_count += 1
            else:
                valid_values.append(val)
        else:
            invalid_type_count += 1

    non_null_count = len(valid_values)
    coverage_percent = (non_null_count / row_count * 100.0) if row_count > 0 else 0.0
    missingness_percent = 100.0 - coverage_percent

    if valid_values:
        minimum = float(np.min(valid_values))
        q1 = float(np.percentile(valid_values, 25))
        median = float(np.median(valid_values))
        q3 = float(np.percentile(valid_values, 75))
        maximum = float(np.max(valid_values))
        unique_count = len(set(valid_values))
        zero_count = sum(1 for v in valid_values if v == 0)
        zero_rate_percent = (zero_count / non_null_count * 100.0) if non_null_count > 0 else 0.0

        if len(valid_values) >= 3 and float(np.var(valid_values)) > 0:
            skew_val = float(pd.Series(valid_values).skew())
            skewness = skew_val if not np.isnan(skew_val) else None
        else:
            skewness = None
    else:
        minimum = None
        q1 = None
        median = None
        q3 = None
        maximum = None
        unique_count = 0
        zero_count = 0
        zero_rate_percent = 0.0
        skewness = None

    return NumericFeatureStats(
        row_count=row_count,
        non_null_count=non_null_count,
        missing_count=missing_count,
        coverage_percent=coverage_percent,
        missingness_percent=missingness_percent,
        observed_dtype=observed_dtype,
        invalid_type_count=invalid_type_count,
        minimum=minimum,
        q1=q1,
        median=median,
        q3=q3,
        maximum=maximum,
        unique_count=unique_count,
        zero_count=zero_count,
        zero_rate_percent=zero_rate_percent,
        skewness=skewness,
    )
