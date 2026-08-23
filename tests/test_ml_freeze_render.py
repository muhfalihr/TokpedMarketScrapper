"""Tests for rendering decision diffs, READMEs, and RELEASE_SIGNOFF.md."""

import pandas as pd
import pytest

from laptop_market_scraper.ml_freeze.render import (
    build_decision_diff,
    render_release_signoff,
)
from laptop_market_scraper.ml_freeze.review_gate import LowPriceReviewGateResult
from laptop_market_scraper.ml_freeze.validate import FreezeValidationResult


def test_decision_diff_records_explicit_artifact_versions():
    prev = pd.DataFrame([
        {
            "listing_key": "k1",
            "product_name": "Laptop A",
            "eligibility_decision": "VALID_LAPTOP",
            "eligibility_reason": "VALID_LAPTOP",
        }
    ])
    curr = pd.DataFrame([
        {
            "listing_key": "k1",
            "product_name": "Laptop A",
            "eligibility_decision": "EXCLUDE",
            "eligibility_reason": "NON_LAPTOP_COMPONENT",
        }
    ])

    diff = build_decision_diff(
        previous_decisions=prev,
        current_decisions=curr,
        previous_artifact="ml-dataset-v1.0.1",
        current_artifact="ml-dataset-v1.0.2",
    )

    assert set(diff["previous_artifact"]) == {"ml-dataset-v1.0.1"}
    assert set(diff["current_artifact"]) == {"ml-dataset-v1.0.2"}
    assert diff.iloc[0]["change_type"] == "VALID_TO_EXCLUDE"


def test_release_signoff_declares_final_only_when_gates_pass():
    manifest = {
        "artifact": "ml-dataset-v1.0.2",
        "source_run_id": "run-123",
        "source_rows": 2227,
        "git_commit": "abcdef",
        "acquisition_tag": "dataset-acquisition-v1.0",
        "cleaning": {"valid_laptop_count": 2163, "excluded_count": 64, "ambiguous_count": 0},
        "representations": {
            "R1": {"features": ["price", "rating"], "rows": 2106, "sha256": "abc"},
            "R2": {"features": ["price", "rating", "review_count"], "rows": 1588, "sha256": "def"},
        },
        "release_review": {
            "low_price_review_required": 20,
            "low_price_review_resolved": 20,
            "approved_valid": 20,
            "leakage": 0,
            "ambiguous": 0,
            "review_decisions_sha256": "12345",
        },
    }

    gate = LowPriceReviewGateResult(
        total_required=20,
        total_resolved=20,
        approved_valid=20,
        leakage=0,
        ambiguous=0,
        missing_listing_keys=(),
        unexpected_listing_keys=(),
        passed=True,
    )
    val = FreezeValidationResult(passed=True)

    rendered = render_release_signoff(
        manifest=manifest,
        review_gate=gate,
        validation=val,
    )

    assert "ML_DATASET_V1_FINAL" in rendered


def test_release_signoff_cannot_declare_final_with_pending_review():
    manifest = {
        "artifact": "ml-dataset-v1.0.2",
        "source_run_id": "run-123",
        "source_rows": 2227,
    }

    gate = LowPriceReviewGateResult(
        total_required=20,
        total_resolved=19,
        approved_valid=19,
        leakage=0,
        ambiguous=0,
        missing_listing_keys=("k20",),
        unexpected_listing_keys=(),
        passed=False,
    )
    val = FreezeValidationResult(passed=False, errors=("incomplete review",))

    rendered = render_release_signoff(
        manifest=manifest,
        review_gate=gate,
        validation=val,
    )

    assert "ML_DATASET_V1_FINAL" not in rendered
    assert "PENDING_RELEASE_SIGNOFF" in rendered
