"""Tests for review_count semantic reconciliation (Task 5)."""

from tokped_market_scrapper.ml_freeze.config import load_ml_freeze_config
from tokped_market_scrapper.ml_freeze.models import ReviewCountSemanticStatus
from tokped_market_scrapper.ml_freeze.review_semantics import resolve_review_count

_CONFIG = load_ml_freeze_config("config/ml_freeze.yaml")


def test_explicit_zero_remains_zero():
    result = resolve_review_count(
        row={"listing_key": "a", "review_count": 0},
        raw=None,
        provenance_rows=(),
        config=_CONFIG,
    )
    assert result.resolved_value == 0
    assert result.semantic_status == ReviewCountSemanticStatus.EXPLICIT_ZERO


def test_observed_review_count_is_preserved():
    result = resolve_review_count(
        row={"listing_key": "a", "review_count": 12},
        raw=None,
        provenance_rows=(),
        config=_CONFIG,
    )
    assert result.resolved_value == 12
    assert result.semantic_status == ReviewCountSemanticStatus.OBSERVED_COUNT


def test_missing_review_count_is_not_silently_zeroed():
    result = resolve_review_count(
        row={"listing_key": "a", "rating": 5.0, "review_count": None},
        raw=None,
        provenance_rows=(),
        config=_CONFIG,
    )
    assert result.original_value is None
    assert result.resolved_value is None
    assert result.semantic_status == ReviewCountSemanticStatus.MISSING_UNRESOLVED


def test_missing_review_with_rating_still_unresolved():
    """rating present + review_count missing must NOT infer zero."""
    result = resolve_review_count(
        row={"listing_key": "b", "rating": 4.5, "review_count": None},
        raw=None,
        provenance_rows=(),
        config=_CONFIG,
    )
    assert result.resolved_value is None
    assert result.semantic_status == ReviewCountSemanticStatus.MISSING_UNRESOLVED
