import numpy as np
import pandas as pd
import pytest

from tokped_market_scrapper.ml_readiness import (
    AssociationConfig,
    DistributionResult,
    ExtremesConfig,
    MLReadinessConfig,
    RepresentationConfig,
    TransformationSignal,
    analyze_all_distributions,
    analyze_distribution,
)


@pytest.fixture
def sample_config() -> MLReadinessConfig:
    return MLReadinessConfig(
        features=["price", "rating", "review_count"],
        representations={
            "r1": RepresentationConfig(
                id="r1", description="R1", features=["price", "rating"]
            ),
        },
        extremes=ExtremesConfig(
            price_lower_quantile=0.01,
            price_upper_quantile=0.99,
            iqr_multiplier=1.5,
            robust_z_threshold=3.5,
            sample_limit=10,
        ),
        association=AssociationConfig(spearman_redundancy_threshold=0.8),
    )


def test_analyze_distribution_percentiles_and_iqr(sample_config):
    data = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
    res = analyze_distribution(data, "price", sample_config)

    assert isinstance(res, DistributionResult)
    assert res.feature_name == "price"
    assert res.non_null_count == 10
    assert res.missing_count == 0
    assert res.coverage_percent == 100.0
    assert res.min_value == 10.0
    assert res.max_value == 100.0
    assert res.q25 == pytest.approx(data.quantile(0.25))
    assert res.q75 == pytest.approx(data.quantile(0.75))
    assert res.iqr == pytest.approx(res.q75 - res.q25)
    assert res.zero_count == 0
    assert res.zero_rate == 0.0
    assert res.zero_variance_flag is False
    assert res.near_zero_variance_flag is False


def test_analyze_distribution_highly_skewed_price_recommended(sample_config):
    np.random.seed(42)
    skewed_data = pd.Series(np.random.lognormal(mean=16.0, sigma=1.5, size=500))
    res = analyze_distribution(skewed_data, "price", sample_config)

    assert res.raw_skewness is not None
    assert res.log1p_skewness is not None
    assert res.absolute_skew_reduction is not None
    assert abs(res.raw_skewness) > 1.0
    assert res.absolute_skew_reduction > 0.5
    assert res.transformation_signal == TransformationSignal.LOG1P_RECOMMENDED


def test_analyze_distribution_moderately_skewed_review_count_optional(sample_config):
    data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 12.0, 18.0, 25.0, 40.0])
    res = analyze_distribution(data, "review_count", sample_config)

    assert res.transformation_signal in (
        TransformationSignal.LOG1P_RECOMMENDED,
        TransformationSignal.LOG1P_OPTIONAL,
    )


def test_analyze_distribution_rating_preserves_not_applicable(sample_config):
    data = pd.Series([4.0, 4.2, 4.5, 4.8, 5.0, 4.9, 4.7, 4.6, 4.1, 4.3])
    res = analyze_distribution(data, "rating", sample_config)

    assert res.transformation_signal == TransformationSignal.NOT_APPLICABLE
    assert res.log1p_skewness is None
    assert res.absolute_skew_reduction is None


def test_analyze_distribution_zero_variance_and_near_zero_variance(sample_config):
    constant_data = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0])
    res_zv = analyze_distribution(constant_data, "rating", sample_config)

    assert res_zv.zero_variance_flag is True
    assert res_zv.near_zero_variance_flag is True
    assert res_zv.unique_value_count == 1
    assert res_zv.dominant_value_rate == 1.0

    near_zv_data = pd.Series([0.0] * 96 + [1.0] * 4)
    res_nzv = analyze_distribution(near_zv_data, "review_count", sample_config)

    assert res_nzv.zero_variance_flag is False
    assert res_nzv.near_zero_variance_flag is True
    assert res_nzv.dominant_value_count == 96
    assert res_nzv.dominant_value_rate == 0.96


def test_analyze_distribution_empty_or_all_null(sample_config):
    data = pd.Series([None, None, None], dtype=float)
    res = analyze_distribution(data, "price", sample_config)

    assert res.non_null_count == 0
    assert res.missing_count == 3
    assert res.coverage_percent == 0.0
    assert res.min_value is None
    assert res.max_value is None
    assert res.zero_variance_flag is True
    assert res.near_zero_variance_flag is False
    assert res.transformation_signal == TransformationSignal.RAW_PRESERVED


def test_analyze_all_distributions(sample_config):
    df = pd.DataFrame(
        {
            "price": [10_000_000.0, 15_000_000.0, 20_000_000.0, None],
            "rating": [4.0, 4.5, 5.0, 4.8],
            "review_count": [0.0, 10.0, 100.0, 5.0],
        }
    )
    results = analyze_all_distributions(df, sample_config)

    assert set(results.keys()) == {"price", "rating", "review_count"}
    assert results["price"].non_null_count == 3
    assert results["price"].missing_count == 1
    assert results["rating"].non_null_count == 4
    assert results["review_count"].zero_count == 1
