import pandas as pd

from laptop_market_scraper.ml_readiness import (
    MissingnessResult,
    MissingSemanticStatus,
    ReadinessDataset,
    analyze_missingness,
    audit_missingness,
)


def make_dataset(
    products_df: pd.DataFrame,
    raw_by_listing_key: dict | None = None,
    provenance_df: pd.DataFrame | None = None,
) -> ReadinessDataset:
    return ReadinessDataset(
        products=products_df,
        provenance=provenance_df if provenance_df is not None else pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key=raw_by_listing_key if raw_by_listing_key is not None else {},
    )


def test_missing_review_count_never_becomes_zero():
    frame = pd.DataFrame(
        [
            {
                "listing_key": "x",
                "price": 10_000_000,
                "rating": 4.9,
                "review_count": None,
                "product_name": "Laptop X",
            }
        ]
    )

    result = analyze_missingness(make_dataset(frame))

    assert len(result.cases) == 1
    case = result.cases[0]

    assert case.review_count is None
    assert case.review_count_missing is True
    assert case.semantic_status in {
        MissingSemanticStatus.AMBIGUOUS,
        MissingSemanticStatus.UNRESOLVED,
    }


def test_joint_missingness_patterns_are_counted():
    frame = pd.DataFrame(
        [
            {"listing_key": "a", "price": 1000.0, "rating": 5.0, "review_count": 4.0},
            {"listing_key": "b", "price": 2000.0, "rating": None, "review_count": 4.0},
            {"listing_key": "c", "price": 3000.0, "rating": 5.0, "review_count": None},
            {"listing_key": "d", "price": 4000.0, "rating": None, "review_count": None},
        ]
    )

    result = analyze_missingness(make_dataset(frame))

    assert isinstance(result, MissingnessResult)
    assert result.total_rows == 4
    assert result.complete_rating_and_reviews == 1
    assert result.missing_rating_only == 1
    assert result.missing_reviews_only == 1
    assert result.missing_both == 1
    assert result.rating_missing_percent == 50.0
    assert result.review_missing_percent == 50.0


def test_median_price_calculation_for_review_present_vs_missing():
    frame = pd.DataFrame(
        [
            {"listing_key": "k1", "price": 10_000_000.0, "rating": 4.5, "review_count": 10.0},
            {"listing_key": "k2", "price": 20_000_000.0, "rating": 5.0, "review_count": 0.0},
            {"listing_key": "k3", "price": 30_000_000.0, "rating": None, "review_count": None},
            {"listing_key": "k4", "price": 50_000_000.0, "rating": 4.0, "review_count": None},
        ]
    )

    result = analyze_missingness(make_dataset(frame))

    # Review present: k1 (10M), k2 (20M) -> Median = 15M
    assert result.median_price_when_review_present == 15_000_000.0
    # Review missing: k3 (30M), k4 (50M) -> Median = 40M
    assert result.median_price_when_review_missing == 40_000_000.0


def test_semantic_status_and_evidence_with_raw_data():
    frame = pd.DataFrame(
        [
            # Supported: raw payload explicitly shows zero reviews
            {"listing_key": "supported_key", "price": 1000.0, "rating": None, "review_count": None},
            # Unresolved: rating present but review_count missing
            {"listing_key": "unresolved_key", "price": 1000.0, "rating": 4.8, "review_count": None},
            # Ambiguous: review_count present but rating missing
            {"listing_key": "ambiguous_key", "price": 1000.0, "rating": None, "review_count": 5.0},
        ]
    )

    raw_data = {
        "supported_key": {
            "listing_key": "supported_key",
            "rating": 0,
            "review_count": 0,
        },
        "unresolved_key": {
            "listing_key": "unresolved_key",
            "rating": 4.8,
        },
    }

    result = analyze_missingness(make_dataset(frame, raw_by_listing_key=raw_data))

    cases_by_key = {c.listing_key: c for c in result.cases}

    assert cases_by_key["supported_key"].semantic_status == MissingSemanticStatus.SUPPORTED
    assert "explicit_no_review_state_in_raw" in cases_by_key["supported_key"].evidence

    assert cases_by_key["unresolved_key"].semantic_status == MissingSemanticStatus.UNRESOLVED
    assert "rating_present_review_missing" in cases_by_key["unresolved_key"].evidence

    assert cases_by_key["ambiguous_key"].semantic_status == MissingSemanticStatus.AMBIGUOUS
    assert "review_present_rating_missing" in cases_by_key["ambiguous_key"].evidence


def test_empty_dataset():
    frame = pd.DataFrame(columns=["listing_key", "price", "rating", "review_count"])
    result = analyze_missingness(make_dataset(frame))

    assert result.total_rows == 0
    assert result.complete_rating_and_reviews == 0
    assert result.missing_rating_only == 0
    assert result.missing_reviews_only == 0
    assert result.missing_both == 0
    assert result.rating_missing_percent == 0.0
    assert result.review_missing_percent == 0.0
    assert result.median_price_when_review_present is None
    assert result.median_price_when_review_missing is None
    assert result.cases == ()


def test_audit_missingness_alias():
    frame = pd.DataFrame([{"listing_key": "a", "price": 1000.0, "rating": 5.0, "review_count": 4.0}])
    res1 = analyze_missingness(make_dataset(frame))
    res2 = audit_missingness(make_dataset(frame))
    assert res1 == res2
