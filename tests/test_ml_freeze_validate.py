"""Tests for ML freeze validator module (Task 8)."""

import pandas as pd

from tokped_market_scrapper.ml_freeze.decisions import build_cleaning_decision
from tokped_market_scrapper.ml_freeze.eligibility import EligibilityAssessment
from tokped_market_scrapper.ml_freeze.matrices import FrozenMatrices
from tokped_market_scrapper.ml_freeze.models import (
    EligibilityDecision,
    EligibilityReason,
    ReviewCountSemanticStatus,
)
from tokped_market_scrapper.ml_freeze.review_semantics import ReviewCountResolution
from tokped_market_scrapper.ml_freeze.validate import validate_frozen_matrices


def _setup_valid_fixture():
    source_products = pd.DataFrame([
        {
            "listing_key": "k1",
            "product_name": "Laptop 1",
            "product_url": "https://tokped.com/1",
            "price": 10_000_000,
            "rating": 4.5,
            "review_count": 10,
        },
        {
            "listing_key": "k2",
            "product_name": "Laptop 2",
            "product_url": "https://tokped.com/2",
            "price": 15_000_000,
            "rating": 4.0,
            "review_count": None,
        },
    ])

    elig_1 = EligibilityAssessment(
        listing_key="k1",
        decision=EligibilityDecision.VALID_LAPTOP,
        reason=EligibilityReason.VALID_LAPTOP,
    )
    elig_2 = EligibilityAssessment(
        listing_key="k2",
        decision=EligibilityDecision.VALID_LAPTOP,
        reason=EligibilityReason.VALID_LAPTOP,
    )

    res_1 = ReviewCountResolution(
        listing_key="k1",
        original_value=10,
        resolved_value=10,
        semantic_status=ReviewCountSemanticStatus.OBSERVED_COUNT,
    )
    res_2 = ReviewCountResolution(
        listing_key="k2",
        original_value=None,
        resolved_value=None,
        semantic_status=ReviewCountSemanticStatus.MISSING_UNRESOLVED,
    )

    dec_1 = build_cleaning_decision(
        row=source_products.iloc[0].to_dict(),
        eligibility=elig_1,
        review_resolution=res_1,
    )
    dec_2 = build_cleaning_decision(
        row=source_products.iloc[1].to_dict(),
        eligibility=elig_2,
        review_resolution=res_2,
    )

    r1 = pd.DataFrame([
        {"listing_key": "k1", "product_name": "Laptop 1", "price": 10_000_000, "rating": 4.5},
        {"listing_key": "k2", "product_name": "Laptop 2", "price": 15_000_000, "rating": 4.0},
    ])

    r2 = pd.DataFrame([
        {
            "listing_key": "k1",
            "product_name": "Laptop 1",
            "price": 10_000_000,
            "rating": 4.5,
            "review_count": 10,
        },
    ])

    matrices = FrozenMatrices(r1=r1, r2=r2)
    decisions = [dec_1, dec_2]

    return source_products, matrices, decisions


def test_validator_passes_valid_matrices():
    source_products, matrices, decisions = _setup_valid_fixture()
    result = validate_frozen_matrices(
        source_products=source_products,
        matrices=matrices,
        decisions=decisions,
    )

    assert result.passed is True
    assert len(result.errors) == 0


def test_validator_rejects_excluded_row_in_matrix():
    source_products, matrices, decisions = _setup_valid_fixture()

    # Modify dec_2 to be EXCLUDE, but keep k2 in R1 matrix
    excluded_elig = EligibilityAssessment(
        listing_key="k2",
        decision=EligibilityDecision.EXCLUDE,
        reason=EligibilityReason.NON_LAPTOP_COMPONENT,
        evidence=("LCD panel",),
    )
    dec_2_excluded = build_cleaning_decision(
        row=source_products.iloc[1].to_dict(),
        eligibility=excluded_elig,
        review_resolution=ReviewCountResolution(
            listing_key="k2",
            original_value=None,
            resolved_value=None,
            semantic_status=ReviewCountSemanticStatus.MISSING_UNRESOLVED,
        ),
    )

    bad_decisions = [decisions[0], dec_2_excluded]

    result = validate_frozen_matrices(
        source_products=source_products,
        matrices=matrices,
        decisions=bad_decisions,
    )

    assert result.passed is False
    assert any("excluded" in err.lower() for err in result.errors)


def test_validator_rejects_ambiguous_row_in_matrix():
    source_products, matrices, decisions = _setup_valid_fixture()

    ambig_elig = EligibilityAssessment(
        listing_key="k2",
        decision=EligibilityDecision.AMBIGUOUS,
        reason=EligibilityReason.AMBIGUOUS_PRODUCT,
        evidence=("conflict",),
    )
    dec_2_ambig = build_cleaning_decision(
        row=source_products.iloc[1].to_dict(),
        eligibility=ambig_elig,
        review_resolution=ReviewCountResolution(
            listing_key="k2",
            original_value=None,
            resolved_value=None,
            semantic_status=ReviewCountSemanticStatus.MISSING_UNRESOLVED,
        ),
    )

    bad_decisions = [decisions[0], dec_2_ambig]

    result = validate_frozen_matrices(
        source_products=source_products,
        matrices=matrices,
        decisions=bad_decisions,
    )

    assert result.passed is False
    assert any("ambiguous" in err.lower() for err in result.errors)


def test_validator_rejects_non_unique_listing_keys():
    source_products, matrices, decisions = _setup_valid_fixture()

    dupe_r1 = pd.concat([matrices.r1, matrices.r1.iloc[[0]]], ignore_index=True)
    bad_matrices = FrozenMatrices(r1=dupe_r1, r2=matrices.r2)

    result = validate_frozen_matrices(
        source_products=source_products,
        matrices=bad_matrices,
        decisions=decisions,
    )

    assert result.passed is False
    assert any("not unique" in err.lower() for err in result.errors)


def test_strict_finalization_fails_when_low_price_review_is_incomplete():
    from tokped_market_scrapper.ml_freeze.review_gate import LowPriceReviewGateResult

    source_products, matrices, decisions = _setup_valid_fixture()
    gate = LowPriceReviewGateResult(
        total_required=20,
        total_resolved=19,
        approved_valid=19,
        leakage=0,
        ambiguous=0,
        missing_listing_keys=("missing-key",),
        unexpected_listing_keys=(),
        passed=False,
    )

    result = validate_frozen_matrices(
        source_products=source_products,
        matrices=matrices,
        decisions=decisions,
        low_price_review_gate=gate,
        require_release_review=True,
    )

    assert result.passed is False
    assert any("manual review" in message.lower() for message in result.errors)

