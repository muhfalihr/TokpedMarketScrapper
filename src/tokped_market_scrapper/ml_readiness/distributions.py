import numpy as np
import pandas as pd

from tokped_market_scrapper.ml_readiness.models import (
    DistributionResult,
    MLReadinessConfig,
    TransformationSignal,
)

SKEW_TRANSFORMABLE_FEATURES: set[str] = {"price", "review_count"}


def analyze_distribution(
    series: pd.Series, feature_name: str, config: MLReadinessConfig
) -> DistributionResult:
    total_count = len(series)
    clean_series = pd.to_numeric(series, errors="coerce").dropna()
    non_null_count = len(clean_series)
    missing_count = total_count - non_null_count
    coverage_percent = (non_null_count / total_count * 100.0) if total_count > 0 else 0.0

    if non_null_count == 0:
        return DistributionResult(
            feature_name=feature_name,
            non_null_count=0,
            missing_count=missing_count,
            coverage_percent=coverage_percent,
            min_value=None,
            q01=None,
            q25=None,
            median=None,
            q75=None,
            q99=None,
            max_value=None,
            iqr=None,
            raw_skewness=None,
            log1p_skewness=None,
            absolute_skew_reduction=None,
            variance=None,
            std_dev=None,
            zero_count=0,
            zero_rate=0.0,
            unique_value_count=0,
            dominant_value_count=0,
            dominant_value_rate=0.0,
            zero_variance_flag=True,
            near_zero_variance_flag=False,
            transformation_signal=(
                TransformationSignal.RAW_PRESERVED
                if feature_name in SKEW_TRANSFORMABLE_FEATURES
                else TransformationSignal.NOT_APPLICABLE
            ),
        )

    min_val = float(clean_series.min())
    q01 = float(clean_series.quantile(0.01))
    q25 = float(clean_series.quantile(0.25))
    median_val = float(clean_series.median())
    q75 = float(clean_series.quantile(0.75))
    q99 = float(clean_series.quantile(0.99))
    max_val = float(clean_series.max())
    iqr_val = float(q75 - q25)

    zero_count = int((clean_series == 0).sum())
    zero_rate = float(zero_count / non_null_count)

    value_counts = clean_series.value_counts()
    unique_value_count = len(value_counts)
    dominant_value_count = int(value_counts.iloc[0]) if not value_counts.empty else 0
    dominant_value_rate = float(dominant_value_count / non_null_count)

    if non_null_count >= 2:
        variance_val = float(clean_series.var())
        std_val = float(clean_series.std())
    else:
        variance_val = 0.0
        std_val = 0.0

    zero_variance_flag = (unique_value_count <= 1) or (variance_val == 0.0)
    near_zero_variance_flag = dominant_value_rate >= 0.95

    raw_skewness: float | None = None
    if non_null_count >= 3 and std_val > 0:
        raw_skew_calc = clean_series.skew()
        if not pd.isna(raw_skew_calc):
            raw_skewness = float(raw_skew_calc)

    log1p_skewness: float | None = None
    absolute_skew_reduction: float | None = None

    if (
        feature_name in SKEW_TRANSFORMABLE_FEATURES
        and (clean_series >= 0).all()
        and non_null_count >= 3
        and std_val > 0
    ):
        log1p_series = np.log1p(clean_series)
        log1p_skew_calc = log1p_series.skew()
        if not pd.isna(log1p_skew_calc) and raw_skewness is not None:
            log1p_skewness = float(log1p_skew_calc)
            absolute_skew_reduction = float(abs(raw_skewness) - abs(log1p_skewness))

    if feature_name in SKEW_TRANSFORMABLE_FEATURES:
        if raw_skewness is not None and absolute_skew_reduction is not None:
            if abs(raw_skewness) > 1.0 and absolute_skew_reduction > 0.5:
                transformation_signal = TransformationSignal.LOG1P_RECOMMENDED
            elif abs(raw_skewness) > 0.5 and absolute_skew_reduction > 0.2:
                transformation_signal = TransformationSignal.LOG1P_OPTIONAL
            else:
                transformation_signal = TransformationSignal.RAW_PRESERVED
        else:
            transformation_signal = TransformationSignal.RAW_PRESERVED
    else:
        transformation_signal = TransformationSignal.NOT_APPLICABLE

    return DistributionResult(
        feature_name=feature_name,
        non_null_count=non_null_count,
        missing_count=missing_count,
        coverage_percent=coverage_percent,
        min_value=min_val,
        q01=q01,
        q25=q25,
        median=median_val,
        q75=q75,
        q99=q99,
        max_value=max_val,
        iqr=iqr_val,
        raw_skewness=raw_skewness,
        log1p_skewness=log1p_skewness,
        absolute_skew_reduction=absolute_skew_reduction,
        variance=variance_val,
        std_dev=std_val,
        zero_count=zero_count,
        zero_rate=zero_rate,
        unique_value_count=unique_value_count,
        dominant_value_count=dominant_value_count,
        dominant_value_rate=dominant_value_rate,
        zero_variance_flag=zero_variance_flag,
        near_zero_variance_flag=near_zero_variance_flag,
        transformation_signal=transformation_signal,
    )


def analyze_all_distributions(
    products_df: pd.DataFrame, config: MLReadinessConfig
) -> dict[str, DistributionResult]:
    results: dict[str, DistributionResult] = {}
    for feature in config.features:
        if feature in products_df.columns:
            series = products_df[feature]
        else:
            series = pd.Series(dtype=float)
        results[feature] = analyze_distribution(series, feature, config)
    return results
