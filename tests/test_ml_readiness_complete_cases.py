import pandas as pd
import pytest

from laptop_market_scraper.ml_readiness import (
    AssociationConfig,
    CompleteCaseResult,
    ExtremesConfig,
    MLReadinessConfig,
    ReadinessDataset,
    RepresentationConfig,
    analyze_all_representations,
    analyze_complete_cases,
)


def make_dataset(products_df: pd.DataFrame) -> ReadinessDataset:
    return ReadinessDataset(
        products=products_df,
        provenance=pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key={},
    )


def test_complete_case_analysis_r1_features():
    df = pd.DataFrame(
        [
            {"listing_key": "k1", "price": 10_000_000.0, "rating": 4.5, "review_count": 10.0},
            {"listing_key": "k2", "price": 20_000_000.0, "rating": 4.8, "review_count": None},
            {"listing_key": "k3", "price": 15_000_000.0, "rating": None, "review_count": 5.0},
            {"listing_key": "k4", "price": None, "rating": 5.0, "review_count": 20.0},
            {"listing_key": "k5", "price": 12_000_000.0, "rating": 4.0, "review_count": 0.0},
        ]
    )
    dataset = make_dataset(df)

    res = analyze_complete_cases(
        dataset, representation_id="r1", required_features=("price", "rating")
    )

    assert isinstance(res, CompleteCaseResult)
    assert res.representation_id == "r1"
    assert res.required_features == ("price", "rating")
    assert res.total_rows == 5
    assert res.complete_rows == 3
    assert res.dropped_rows == 2
    assert pytest.approx(res.retention_percent) == 60.0
    assert pytest.approx(res.dropped_percent) == 40.0
    assert res.complete_listing_keys == ("k1", "k2", "k5")


def test_complete_case_analysis_r2_features():
    df = pd.DataFrame(
        [
            {"listing_key": "k1", "price": 10_000_000.0, "rating": 4.5, "review_count": 10.0},
            {"listing_key": "k2", "price": 20_000_000.0, "rating": 4.8, "review_count": None},
            {"listing_key": "k3", "price": 15_000_000.0, "rating": None, "review_count": 5.0},
            {"listing_key": "k4", "price": None, "rating": 5.0, "review_count": 20.0},
            {"listing_key": "k5", "price": 12_000_000.0, "rating": 4.0, "review_count": 0.0},
        ]
    )
    dataset = make_dataset(df)

    res = analyze_complete_cases(
        dataset,
        representation_id="r2",
        required_features=("price", "rating", "review_count"),
    )

    assert isinstance(res, CompleteCaseResult)
    assert res.representation_id == "r2"
    assert res.required_features == ("price", "rating", "review_count")
    assert res.total_rows == 5
    assert res.complete_rows == 2
    assert res.dropped_rows == 3
    assert pytest.approx(res.retention_percent) == 40.0
    assert pytest.approx(res.dropped_percent) == 60.0
    assert res.complete_listing_keys == ("k1", "k5")


def test_complete_case_analysis_empty_dataset():
    df = pd.DataFrame(columns=["listing_key", "price", "rating", "review_count"])
    dataset = make_dataset(df)

    res = analyze_complete_cases(
        dataset, representation_id="r1", required_features=("price", "rating")
    )

    assert isinstance(res, CompleteCaseResult)
    assert res.total_rows == 0
    assert res.complete_rows == 0
    assert res.dropped_rows == 0
    assert res.retention_percent == 0.0
    assert res.dropped_percent == 0.0
    assert res.complete_listing_keys == ()


def test_analyze_all_representations():
    df = pd.DataFrame(
        [
            {"listing_key": "k1", "price": 10_000_000.0, "rating": 4.5, "review_count": 10.0},
            {"listing_key": "k2", "price": 20_000_000.0, "rating": 4.8, "review_count": None},
        ]
    )
    dataset = make_dataset(df)

    config = MLReadinessConfig(
        features=["price", "rating", "review_count"],
        representations={
            "r1": RepresentationConfig(
                id="r1", description="R1", features=["price", "rating"]
            ),
            "r2": RepresentationConfig(
                id="r2", description="R2", features=["price", "rating", "review_count"]
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

    results = analyze_all_representations(dataset, config)

    assert set(results.keys()) == {"r1", "r2"}
    assert results["r1"].complete_rows == 2
    assert results["r2"].complete_rows == 1


def test_complete_case_missing_required_column():
    df = pd.DataFrame(
        [
            {"listing_key": "k1", "price": 10_000_000.0, "rating": 4.5},
            {"listing_key": "k2", "price": 20_000_000.0, "rating": 4.8},
        ]
    )
    dataset = make_dataset(df)

    res = analyze_complete_cases(
        dataset,
        representation_id="r2",
        required_features=("price", "rating", "review_count"),
    )

    assert res.total_rows == 2
    assert res.complete_rows == 0
    assert res.dropped_rows == 2
    assert res.retention_percent == 0.0
    assert res.dropped_percent == 100.0
    assert res.complete_listing_keys == ()
