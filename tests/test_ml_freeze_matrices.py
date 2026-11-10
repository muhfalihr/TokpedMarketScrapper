"""Tests for ML freeze matrices module (Task 7)."""

import pandas as pd

from laptop_market_scraper.ml_freeze.decisions import build_cleaning_decision
from laptop_market_scraper.ml_freeze.eligibility import EligibilityAssessment
from laptop_market_scraper.ml_freeze.matrices import build_ml_matrices
from laptop_market_scraper.ml_freeze.models import (
    EligibilityDecision,
    EligibilityReason,
    ReviewCountSemanticStatus,
)
from laptop_market_scraper.ml_freeze.review_semantics import ReviewCountResolution


def build_test_matrices():
    products = pd.DataFrame([
        {
            "listing_key": "b",
            "product_name": "Laptop B",
            "product_url": "https://tokped.com/b",
            "price": 20_000_000,
            "rating": 4.8,
            "review_count": None,
        },
        {
            "listing_key": "a",
            "product_name": "Laptop A",
            "product_url": "https://tokped.com/a",
            "price": 10_000_000,
            "rating": 4.5,
            "review_count": 15,
        },
    ])

    eligibility = {
        "a": EligibilityAssessment(
            listing_key="a",
            decision=EligibilityDecision.VALID_LAPTOP,
            reason=EligibilityReason.VALID_LAPTOP,
        ),
        "b": EligibilityAssessment(
            listing_key="b",
            decision=EligibilityDecision.VALID_LAPTOP,
            reason=EligibilityReason.VALID_LAPTOP,
        ),
    }

    review_resolutions = {
        "a": ReviewCountResolution(
            listing_key="a",
            original_value=15,
            resolved_value=15,
            semantic_status=ReviewCountSemanticStatus.OBSERVED_COUNT,
        ),
        "b": ReviewCountResolution(
            listing_key="b",
            original_value=None,
            resolved_value=None,
            semantic_status=ReviewCountSemanticStatus.MISSING_UNRESOLVED,
        ),
    }

    decisions = [
        build_cleaning_decision(
            row=products.iloc[0].to_dict(),
            eligibility=eligibility["b"],
            review_resolution=review_resolutions["b"],
        ),
        build_cleaning_decision(
            row=products.iloc[1].to_dict(),
            eligibility=eligibility["a"],
            review_resolution=review_resolutions["a"],
        ),
    ]

    identity_columns = ("listing_key", "product_name", "product_url")

    return build_ml_matrices(
        products=products,
        decisions=decisions,
        review_resolutions=review_resolutions,
        identity_columns=identity_columns,
    )


def test_matrices_are_materialized_independently():
    matrices = build_test_matrices()

    assert list(matrices.r1[["price", "rating"]].columns) == ["price", "rating"]
    assert list(matrices.r2[["price", "rating", "review_count"]].columns) == [
        "price",
        "rating",
        "review_count",
    ]

    # R1 has both products, R2 has only 'a' because 'b' has missing review_count
    assert len(matrices.r1) == 2
    assert len(matrices.r2) == 1
    assert len(matrices.r1) >= len(matrices.r2)


def test_model_feature_columns_are_complete_cases():
    matrices = build_test_matrices()

    assert not matrices.r1[["price", "rating"]].isna().any().any()
    assert not matrices.r2[["price", "rating", "review_count"]].isna().any().any()


def test_matrices_are_sorted_by_listing_key_asc():
    matrices = build_test_matrices()

    assert list(matrices.r1["listing_key"]) == ["a", "b"]
    assert list(matrices.r2["listing_key"]) == ["a"]
