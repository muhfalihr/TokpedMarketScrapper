"""Materialize R1 and R2 frozen matrices from cleaning decisions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from tokped_market_scrapper.ml_freeze.models import CleaningDecision
from tokped_market_scrapper.ml_freeze.review_semantics import ReviewCountResolution


@dataclass(frozen=True)
class FrozenMatrices:
    r1: pd.DataFrame
    r2: pd.DataFrame


def build_ml_matrices(
    *,
    products: pd.DataFrame,
    decisions: Sequence[CleaningDecision],
    review_resolutions: Mapping[str, ReviewCountResolution],
    identity_columns: tuple[str, ...],
) -> FrozenMatrices:
    """Build R1 and R2 ML matrices from products, decisions, and review resolutions.

    R1: identity_columns + price + rating (complete cases only).
    R2: identity_columns + price + rating + review_count (complete cases only).

    Both sorted by listing_key ASC for deterministic output.
    """
    # Build R1: products included in R1
    r1_keys = [d.listing_key for d in decisions if d.include_r1]
    r1_mask = products["listing_key"].isin(r1_keys)
    r1_cols = list(identity_columns) + ["price", "rating"]
    # Ensure no duplicates in column list
    r1_cols = list(dict.fromkeys(r1_cols))
    r1 = products.loc[r1_mask, r1_cols].copy()
    r1 = r1.sort_values("listing_key").reset_index(drop=True)

    # Build R2: products included in R2, with resolved review_count
    r2_keys = [d.listing_key for d in decisions if d.include_r2]
    r2_mask = products["listing_key"].isin(r2_keys)
    r2_cols = list(identity_columns) + ["price", "rating", "review_count"]
    r2_cols = list(dict.fromkeys(r2_cols))
    r2 = products.loc[r2_mask, r2_cols].copy()

    # Replace review_count with resolved values
    r2["review_count"] = r2["listing_key"].map(
        lambda k: review_resolutions[k].resolved_value
        if k in review_resolutions
        else None
    )
    r2 = r2.sort_values("listing_key").reset_index(drop=True)

    return FrozenMatrices(r1=r1, r2=r2)
