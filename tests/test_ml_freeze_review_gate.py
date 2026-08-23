"""Tests for low-price manual review contracts and gate validation."""

from pathlib import Path
import pandas as pd
import pytest
from pydantic import ValidationError

from laptop_market_scraper.ml_freeze.models import ManualReviewStatus, LowPriceReviewDecision
from laptop_market_scraper.ml_freeze.review_gate import (
    load_low_price_review_decisions,
    validate_low_price_review_gate,
)


def test_low_price_review_gate_requires_exact_listing_key_coverage():
    required = pd.DataFrame(
        [
            {"listing_key": "a"},
            {"listing_key": "b"},
        ]
    )

    decisions = (
        LowPriceReviewDecision(
            listing_key="a",
            review_status=ManualReviewStatus.APPROVED_VALID,
            review_note="Used laptop listing; primary product is laptop.",
        ),
    )

    result = validate_low_price_review_gate(
        required_review=required,
        decisions=decisions,
    )

    assert result.passed is False
    assert result.missing_listing_keys == ("b",)


def test_manual_review_requires_non_empty_evidence_note():
    with pytest.raises(ValidationError):
        LowPriceReviewDecision(
            listing_key="a",
            review_status=ManualReviewStatus.APPROVED_VALID,
            review_note="",
        )


def test_load_low_price_review_decisions_from_csv(tmp_path: Path):
    csv_path = tmp_path / "low_price_review_decisions.csv"
    csv_path.write_text(
        "listing_key,review_status,review_note\n"
        "key-1,APPROVED_VALID,Valid used laptop\n"
        "key-2,LEAKAGE,Accessory item\n",
        encoding="utf-8",
    )

    decisions = load_low_price_review_decisions(csv_path)
    assert len(decisions) == 2
    assert decisions[0].listing_key == "key-1"
    assert decisions[0].review_status == ManualReviewStatus.APPROVED_VALID
    assert decisions[1].review_status == ManualReviewStatus.LEAKAGE
