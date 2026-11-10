"""Reconcile review_count missing-value semantics for ML dataset freeze.

Never converts null review_count to zero from absence alone.
Explicit zero stays zero. Missing stays missing (MISSING_UNRESOLVED).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
from pydantic import BaseModel

from tokped_market_scrapper.ml_freeze.models import (
    MLFreezeConfig,
    ReviewCountSemanticStatus,
)


class ReviewCountResolution(BaseModel):
    listing_key: str
    original_value: int | None
    resolved_value: int | None
    semantic_status: ReviewCountSemanticStatus
    evidence: tuple[str, ...] = ()


def resolve_review_count(
    *,
    row: Mapping[str, Any],
    raw: Mapping[str, Any] | None,
    provenance_rows: Sequence[Mapping[str, Any]],
    config: MLFreezeConfig,
) -> ReviewCountResolution:
    """Resolve review_count semantics for a single product.

    Rules:
    - observed numeric > 0  → OBSERVED_COUNT, keep value
    - observed numeric = 0  → EXPLICIT_ZERO, keep 0
    - null                  → MISSING_UNRESOLVED, keep None

    SEMANTIC_ZERO_PROVEN is only allowed when allow_semantic_zero_recode=True
    AND explicit evidence proves absence means zero.
    """
    listing_key = str(row.get("listing_key", ""))
    review_count = row.get("review_count")
    evidence: list[str] = []

    # Handle None / missing / NaN
    if review_count is None or pd.isna(review_count):
        evidence.append("review_count is null/missing")

        # Only recode to zero if explicitly enabled and evidence proves it
        if config.review_count.allow_semantic_zero_recode:
            # TODO: Check provenance/raw for explicit evidence that absence means zero
            # For now, no semantic zero recode rule has been proven
            pass

        return ReviewCountResolution(
            listing_key=listing_key,
            original_value=None,
            resolved_value=None,
            semantic_status=ReviewCountSemanticStatus.MISSING_UNRESOLVED,
            evidence=tuple(evidence),
        )

    # Convert to int for comparison
    count = int(review_count)

    if count == 0:
        evidence.append("review_count is explicitly 0")
        return ReviewCountResolution(
            listing_key=listing_key,
            original_value=0,
            resolved_value=0,
            semantic_status=ReviewCountSemanticStatus.EXPLICIT_ZERO,
            evidence=tuple(evidence),
        )

    # Positive observed count
    evidence.append(f"review_count is observed: {count}")
    return ReviewCountResolution(
        listing_key=listing_key,
        original_value=count,
        resolved_value=count,
        semantic_status=ReviewCountSemanticStatus.OBSERVED_COUNT,
        evidence=tuple(evidence),
    )
