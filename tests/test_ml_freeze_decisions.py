"""Tests for cleaning decision ledger (Task 6)."""

from tokped_market_scrapper.ml_freeze.decisions import build_cleaning_decision
from tokped_market_scrapper.ml_freeze.eligibility import EligibilityAssessment
from tokped_market_scrapper.ml_freeze.models import (
    EligibilityDecision,
    EligibilityReason,
    ReviewCountSemanticStatus,
)
from tokped_market_scrapper.ml_freeze.review_semantics import ReviewCountResolution


def _valid_eligibility(key: str) -> EligibilityAssessment:
    return EligibilityAssessment(
        listing_key=key,
        decision=EligibilityDecision.VALID_LAPTOP,
        reason=EligibilityReason.VALID_LAPTOP,
    )


def _excluded_eligibility(key: str) -> EligibilityAssessment:
    return EligibilityAssessment(
        listing_key=key,
        decision=EligibilityDecision.EXCLUDE,
        reason=EligibilityReason.NON_LAPTOP_COMPONENT,
        evidence=("title contains component term 'lcd'",),
    )


def _missing_review(key: str) -> ReviewCountResolution:
    return ReviewCountResolution(
        listing_key=key,
        original_value=None,
        resolved_value=None,
        semantic_status=ReviewCountSemanticStatus.MISSING_UNRESOLVED,
    )


def _observed_review(key: str, count: int) -> ReviewCountResolution:
    return ReviewCountResolution(
        listing_key=key,
        original_value=count,
        resolved_value=count,
        semantic_status=ReviewCountSemanticStatus.OBSERVED_COUNT,
    )


def test_missing_review_can_enter_r1_but_not_r2():
    decision = build_cleaning_decision(
        row={"listing_key": "a", "price": 15_000_000, "rating": 5.0, "review_count": None},
        eligibility=_valid_eligibility("a"),
        review_resolution=_missing_review("a"),
    )
    assert decision.include_r1 is True
    assert decision.include_r2 is False


def test_non_laptop_is_excluded_from_both():
    decision = build_cleaning_decision(
        row={"listing_key": "lcd", "price": 500_000, "rating": 5.0, "review_count": 3},
        eligibility=_excluded_eligibility("lcd"),
        review_resolution=_observed_review("lcd", 3),
    )
    assert decision.include_r1 is False
    assert decision.include_r2 is False


def test_complete_valid_product_in_both_matrices():
    decision = build_cleaning_decision(
        row={"listing_key": "ok", "price": 10_000_000, "rating": 4.5, "review_count": 10},
        eligibility=_valid_eligibility("ok"),
        review_resolution=_observed_review("ok", 10),
    )
    assert decision.include_r1 is True
    assert decision.include_r2 is True


def test_null_rating_excluded_from_both():
    decision = build_cleaning_decision(
        row={"listing_key": "nr", "price": 10_000_000, "rating": None, "review_count": 5},
        eligibility=_valid_eligibility("nr"),
        review_resolution=_observed_review("nr", 5),
    )
    assert decision.include_r1 is False
    assert decision.include_r2 is False


def test_exclusion_always_has_reason():
    decision = build_cleaning_decision(
        row={"listing_key": "x", "price": None, "rating": None, "review_count": None},
        eligibility=_valid_eligibility("x"),
        review_resolution=_missing_review("x"),
    )
    if not decision.include_r1:
        assert len(decision.exclusion_reasons_r1) > 0
    if not decision.include_r2:
        assert len(decision.exclusion_reasons_r2) > 0
