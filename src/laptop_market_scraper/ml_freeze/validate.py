"""Freeze validation gates for ML datasets.

Validates that frozen matrices satisfy all required invariants.
Never repairs data — only reports errors.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from pydantic import BaseModel

from laptop_market_scraper.ml_freeze.matrices import FrozenMatrices
from laptop_market_scraper.ml_freeze.models import CleaningDecision, EligibilityDecision
from laptop_market_scraper.ml_freeze.review_gate import LowPriceReviewGateResult


class FreezeValidationResult(BaseModel):
    passed: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def validate_frozen_matrices(
    *,
    source_products: pd.DataFrame,
    matrices: FrozenMatrices,
    decisions: Sequence[CleaningDecision],
    low_price_review_gate: LowPriceReviewGateResult | None = None,
    require_release_review: bool = False,
) -> FreezeValidationResult:
    """Validate frozen ML matrices against all required gates.

    Hard gates:
    - R1/R2 listing_key unique
    - R1/R2 listing_key subset of source
    - R1 price/rating no null
    - R2 price/rating/review_count no null
    - price > 0, 0 <= rating <= 5, review_count >= 0
    - No EXCLUDE or AMBIGUOUS decisions in R1/R2
    - Every source listing has exactly one CleaningDecision
    - Every exclusion has at least one reason
    """
    errors: list[str] = []
    warnings: list[str] = []
    source_keys = set(source_products["listing_key"])
    decisions_map = {d.listing_key: d for d in decisions}

    # --- Listing key uniqueness ---
    if not matrices.r1["listing_key"].is_unique:
        errors.append("R1 listing_key is not unique")
    if not matrices.r2["listing_key"].is_unique:
        errors.append("R2 listing_key is not unique")

    # --- Subset of source ---
    r1_keys = set(matrices.r1["listing_key"])
    r2_keys = set(matrices.r2["listing_key"])
    if not r1_keys.issubset(source_keys):
        errors.append(f"R1 contains keys not in source: {r1_keys - source_keys}")
    if not r2_keys.issubset(source_keys):
        errors.append(f"R2 contains keys not in source: {r2_keys - source_keys}")

    # --- Null checks ---
    if matrices.r1[["price", "rating"]].isna().any().any():
        errors.append("R1 contains null values in price or rating")
    if (
        "review_count" in matrices.r2.columns
        and matrices.r2[["price", "rating", "review_count"]].isna().any().any()
    ):
        errors.append("R2 contains null values in price, rating, or review_count")

    # --- Value range checks ---
    if len(matrices.r1) > 0:
        if (matrices.r1["price"] <= 0).any():
            errors.append("R1 contains price <= 0")
        if (matrices.r1["rating"] < 0).any() or (matrices.r1["rating"] > 5).any():
            errors.append("R1 contains rating outside [0, 5]")

    if len(matrices.r2) > 0:
        if (matrices.r2["price"] <= 0).any():
            errors.append("R2 contains price <= 0")
        if (matrices.r2["rating"] < 0).any() or (matrices.r2["rating"] > 5).any():
            errors.append("R2 contains rating outside [0, 5]")
        if "review_count" in matrices.r2.columns and (matrices.r2["review_count"] < 0).any():
            errors.append("R2 contains review_count < 0")

    # --- No excluded/ambiguous in matrices ---
    for key in r1_keys:
        if key in decisions_map:
            d = decisions_map[key]
            if d.eligibility_decision == EligibilityDecision.EXCLUDE:
                errors.append(f"R1 contains excluded row: {key}")
            if d.eligibility_decision == EligibilityDecision.AMBIGUOUS:
                errors.append(f"R1 contains ambiguous row: {key}")

    for key in r2_keys:
        if key in decisions_map:
            d = decisions_map[key]
            if d.eligibility_decision == EligibilityDecision.EXCLUDE:
                errors.append(f"R2 contains excluded row: {key}")
            if d.eligibility_decision == EligibilityDecision.AMBIGUOUS:
                errors.append(f"R2 contains ambiguous row: {key}")

    # --- Every source listing has exactly one decision ---
    if set(decisions_map.keys()) != source_keys:
        missing = source_keys - set(decisions_map.keys())
        extra = set(decisions_map.keys()) - source_keys
        if missing:
            errors.append(f"Source listings without decisions: {sorted(missing)[:5]}")
        if extra:
            errors.append(f"Decisions for non-source listings: {sorted(extra)[:5]}")

    # --- Every exclusion has at least one reason ---
    for d in decisions:
        if not d.include_r1 and not d.exclusion_reasons_r1:
            errors.append(f"R1 exclusion without reason: {d.listing_key}")
        if not d.include_r2 and not d.exclusion_reasons_r2:
            errors.append(f"R2 exclusion without reason: {d.listing_key}")

    # --- Manual review gate check ---
    if require_release_review:
        if low_price_review_gate is None:
            errors.append("Manual review gate required for strict release, but low_price_review_gate is None")
        elif not low_price_review_gate.passed:
            errors.append(
                f"Manual review gate failed or incomplete: {low_price_review_gate.total_resolved}/{low_price_review_gate.total_required} resolved"
            )
    elif low_price_review_gate is not None and not low_price_review_gate.passed:
        warnings.append(
            f"Manual review gate incomplete: {low_price_review_gate.total_resolved}/{low_price_review_gate.total_required} resolved"
        )

    return FreezeValidationResult(
        passed=len(errors) == 0,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
