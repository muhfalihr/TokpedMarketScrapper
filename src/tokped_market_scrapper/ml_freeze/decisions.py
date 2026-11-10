"""Build cleaning decisions for every product in the ML dataset.

Each product gets exactly one CleaningDecision that determines R1/R2 inclusion.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from tokped_market_scrapper.ml_freeze.eligibility import EligibilityAssessment
from tokped_market_scrapper.ml_freeze.models import (
    CleaningDecision,
    EligibilityDecision,
)
from tokped_market_scrapper.ml_freeze.review_semantics import ReviewCountResolution


def build_cleaning_decision(
    *,
    row: Mapping[str, Any],
    eligibility: EligibilityAssessment,
    review_resolution: ReviewCountResolution,
) -> CleaningDecision:
    """Build a cleaning decision for one product.

    R1 inclusion: VALID_LAPTOP AND price not null AND rating not null.
    R2 inclusion: R1 criteria AND resolved review_count not null.

    AMBIGUOUS and EXCLUDE are excluded from both.
    """
    listing_key = str(row.get("listing_key", ""))
    price = row.get("price")
    rating = row.get("rating")

    exclusion_r1: list[str] = []
    exclusion_r2: list[str] = []
    evidence: list[str] = list(eligibility.evidence)

    # Eligibility gate
    if eligibility.decision == EligibilityDecision.EXCLUDE:
        exclusion_r1.append(f"excluded: {eligibility.reason.value}")
        exclusion_r2.append(f"excluded: {eligibility.reason.value}")
    elif eligibility.decision == EligibilityDecision.AMBIGUOUS:
        exclusion_r1.append("ambiguous product")
        exclusion_r2.append("ambiguous product")

    # Price/rating null gate for R1
    if price is None or pd.isna(price):
        exclusion_r1.append("price is null")
        exclusion_r2.append("price is null")
    if rating is None or pd.isna(rating):
        exclusion_r1.append("rating is null")
        exclusion_r2.append("rating is null")

    # Review count gate for R2
    if review_resolution.resolved_value is None:
        exclusion_r2.append(
            f"review_count unresolved: {review_resolution.semantic_status.value}"
        )

    include_r1 = len(exclusion_r1) == 0
    include_r2 = len(exclusion_r2) == 0

    # Add review resolution evidence
    evidence.extend(review_resolution.evidence)

    return CleaningDecision(
        listing_key=listing_key,
        eligibility_decision=eligibility.decision,
        eligibility_reason=eligibility.reason,
        review_count_status=review_resolution.semantic_status,
        include_r1=include_r1,
        include_r2=include_r2,
        exclusion_reasons_r1=tuple(exclusion_r1),
        exclusion_reasons_r2=tuple(exclusion_r2),
        evidence=tuple(evidence),
    )
