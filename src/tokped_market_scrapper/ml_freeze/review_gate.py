"""Low-price manual review contracts and gate validator."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tokped_market_scrapper.ml_freeze.models import LowPriceReviewDecision, ManualReviewStatus


@dataclass(frozen=True)
class LowPriceReviewGateResult:
    total_required: int
    total_resolved: int
    approved_valid: int
    leakage: int
    ambiguous: int
    missing_listing_keys: tuple[str, ...]
    unexpected_listing_keys: tuple[str, ...]
    passed: bool


def load_low_price_review_decisions(path: Path) -> tuple[LowPriceReviewDecision, ...]:
    """Load and validate low_price_review_decisions.csv."""
    if not path.exists():
        raise FileNotFoundError(f"Low-price review decision file not found: {path}")

    df = pd.read_csv(path)
    required_cols = {"listing_key", "review_status", "review_note"}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise ValueError(f"Missing required columns in review decisions CSV: {missing}")

    if df["listing_key"].duplicated().any():
        dups = df[df["listing_key"].duplicated()]["listing_key"].tolist()
        raise ValueError(f"Duplicate listing keys found in review decisions CSV: {dups}")

    decisions: list[LowPriceReviewDecision] = []
    for idx, row in df.iterrows():
        key = str(row["listing_key"]).strip()
        status_str = str(row["review_status"]).strip()
        note = str(row["review_note"]) if pd.notna(row["review_note"]) else ""

        try:
            status = ManualReviewStatus(status_str)
        except ValueError:
            raise ValueError(f"Row {idx}: Invalid review_status '{status_str}' for listing '{key}'")

        decisions.append(
            LowPriceReviewDecision(
                listing_key=key,
                review_status=status,
                review_note=note,
            )
        )

    return tuple(decisions)


def validate_low_price_review_gate(
    *,
    required_review: pd.DataFrame,
    decisions: Sequence[LowPriceReviewDecision],
) -> LowPriceReviewGateResult:
    """Validate that low price review decisions match the required review queue exactly."""
    req_keys = tuple(sorted(required_review["listing_key"].astype(str).unique())) if not required_review.empty else ()
    dec_map = {d.listing_key: d for d in decisions}
    dec_keys = tuple(sorted(dec_map.keys()))

    req_set = set(req_keys)
    dec_set = set(dec_keys)

    missing = tuple(sorted(req_set - dec_set))
    unexpected = tuple(sorted(dec_set - req_set))

    total_required = len(req_keys)
    total_resolved = len(req_set.intersection(dec_set))

    approved_valid = sum(1 for k in req_keys if k in dec_map and dec_map[k].review_status == ManualReviewStatus.APPROVED_VALID)
    leakage = sum(1 for k in req_keys if k in dec_map and dec_map[k].review_status == ManualReviewStatus.LEAKAGE)
    ambiguous = sum(1 for k in req_keys if k in dec_map and dec_map[k].review_status == ManualReviewStatus.AMBIGUOUS)

    passed = len(missing) == 0 and len(unexpected) == 0 and (total_required == total_resolved)

    return LowPriceReviewGateResult(
        total_required=total_required,
        total_resolved=total_resolved,
        approved_valid=approved_valid,
        leakage=leakage,
        ambiguous=ambiguous,
        missing_listing_keys=missing,
        unexpected_listing_keys=unexpected,
        passed=passed,
    )
