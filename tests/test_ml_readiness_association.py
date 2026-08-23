import numpy as np
import pandas as pd
import pytest

from laptop_market_scraper.ml_readiness.association import (
    analyze_associations,
    audit_associations,
)
from laptop_market_scraper.ml_readiness.models import AssociationResult


def test_spearman_detects_monotonic_relation():
    frame = pd.DataFrame(
        {
            "price": [1.0, 2.0, 3.0, 4.0, 5.0],
            "review_count": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )

    results = analyze_associations(
        frame,
        features=("price", "review_count"),
        spearman_redundancy_threshold=0.85,
    )

    assert len(results) == 1
    res = results[0]
    assert isinstance(res, AssociationResult)
    assert res.feature_a == "price"
    assert res.feature_b == "review_count"
    assert res.pairwise_n == 5
    assert res.spearman_rho == pytest.approx(1.0)
    assert res.pearson_r == pytest.approx(1.0)
    assert res.strength == "strong"
    assert res.redundancy_review is True


def test_pairwise_n_excludes_missing_values():
    frame = pd.DataFrame(
        {
            "price": [1.0, 2.0, 3.0, 4.0],
            "rating": [4.0, None, 4.8, None],
        }
    )

    results = analyze_associations(
        frame,
        features=("price", "rating"),
        spearman_redundancy_threshold=0.85,
    )

    assert len(results) == 1
    res = results[0]
    assert res.pairwise_n == 2
    assert res.spearman_rho is None
    assert res.pearson_r is None
    assert res.strength is None
    assert res.redundancy_review is False


def test_zero_variance_returns_none():
    frame = pd.DataFrame(
        {
            "price": [10.0, 10.0, 10.0, 10.0, 10.0],
            "rating": [4.0, 4.2, 4.5, 4.8, 5.0],
        }
    )

    results = analyze_associations(
        frame,
        features=("price", "rating"),
        spearman_redundancy_threshold=0.85,
    )

    assert len(results) == 1
    res = results[0]
    assert res.pairwise_n == 5
    assert res.spearman_rho is None
    assert res.pearson_r is None
    assert res.strength is None
    assert res.redundancy_review is False


def test_strength_classification_and_threshold():
    # Weak association
    frame_weak = pd.DataFrame(
        {
            "price": [10.0, 20.0, 30.0, 40.0, 50.0],
            "rating": [5.0, 1.0, 4.0, 2.0, 3.0],
        }
    )
    res_weak = analyze_associations(
        frame_weak,
        features=("price", "rating"),
        spearman_redundancy_threshold=0.85,
    )[0]
    assert res_weak.strength in ("weak", "moderate")
    assert res_weak.redundancy_review is False

    # Custom threshold trigger
    frame_strong = pd.DataFrame(
        {
            "price": [1.0, 2.0, 3.0, 4.0, 5.0],
            "review_count": [1.0, 2.0, 4.0, 3.0, 5.0],  # high spearman correlation (~0.9)
        }
    )
    res_custom = analyze_associations(
        frame_strong,
        features=("price", "review_count"),
        spearman_redundancy_threshold=0.80,
    )[0]
    assert res_custom.strength == "strong"
    assert res_custom.redundancy_review is True


def test_association_audit_does_not_mutate_source_data():
    frame = pd.DataFrame(
        {
            "price": [100.0, 200.0, 300.0, np.nan],
            "rating": [4.0, 4.5, np.nan, 4.8],
            "review_count": [10.0, 20.0, 30.0, 40.0],
        }
    )
    original = frame.copy(deep=True)

    analyze_associations(
        frame,
        features=("price", "rating", "review_count"),
        spearman_redundancy_threshold=0.85,
    )

    pd.testing.assert_frame_equal(frame, original)


def test_multiple_features_pairwise_combinations():
    frame = pd.DataFrame(
        {
            "price": [10.0, 20.0, 30.0, 40.0],
            "rating": [4.0, 4.2, 4.4, 4.6],
            "review_count": [100.0, 200.0, 300.0, 400.0],
        }
    )

    results = analyze_associations(
        frame,
        features=("price", "rating", "review_count"),
        spearman_redundancy_threshold=0.85,
    )

    assert len(results) == 3
    pairs = [(r.feature_a, r.feature_b) for r in results]
    assert ("price", "rating") in pairs
    assert ("price", "review_count") in pairs
    assert ("rating", "review_count") in pairs


def test_audit_associations_alias():
    frame = pd.DataFrame(
        {
            "price": [1.0, 2.0, 3.0, 4.0, 5.0],
            "review_count": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )

    res1 = analyze_associations(frame, features=("price", "review_count"))
    res2 = audit_associations(frame, features=("price", "review_count"))

    assert res1 == res2
