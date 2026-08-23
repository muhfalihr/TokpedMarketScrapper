"""Render cleaning evidence artifacts (CSVs) for ML dataset freeze."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from laptop_market_scraper.ml_freeze.models import CleaningDecision, EligibilityDecision
from laptop_market_scraper.ml_freeze.review_semantics import ReviewCountResolution


def write_cleaning_artifacts(
    *,
    decisions: Sequence[CleaningDecision],
    review_resolutions: dict[str, ReviewCountResolution],
    products: pd.DataFrame,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Write cleaning_decisions.csv, excluded_observations.csv, ambiguous_observations.csv.

    Returns paths to the three CSV files.
    CSV row order: listing_key ASC.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    products_map = {}
    for _, row in products.iterrows():
        products_map[row["listing_key"]] = row

    records = []
    for d in sorted(decisions, key=lambda x: x.listing_key):
        prod = products_map.get(d.listing_key, {})
        resolution = review_resolutions.get(d.listing_key)
        records.append({
            "listing_key": d.listing_key,
            "product_name": prod.get("product_name", ""),
            "product_url": prod.get("product_url", ""),
            "price": prod.get("price"),
            "rating": prod.get("rating"),
            "review_count_original": resolution.original_value if resolution else None,
            "review_count_resolved": resolution.resolved_value if resolution else None,
            "eligibility_decision": d.eligibility_decision.value,
            "eligibility_reason": d.eligibility_reason.value,
            "review_count_status": d.review_count_status.value,
            "include_r1": d.include_r1,
            "include_r2": d.include_r2,
            "exclusion_reasons_r1": "; ".join(d.exclusion_reasons_r1),
            "exclusion_reasons_r2": "; ".join(d.exclusion_reasons_r2),
            "evidence": "; ".join(d.evidence),
        })

    cleaning_df = pd.DataFrame(records)
    cleaning_path = output_dir / "cleaning_decisions.csv"
    cleaning_df.to_csv(cleaning_path, index=False)

    # Excluded observations
    excluded_df = cleaning_df[
        cleaning_df["eligibility_decision"] == EligibilityDecision.EXCLUDE.value
    ].copy()
    excluded_path = output_dir / "excluded_observations.csv"
    excluded_df.to_csv(excluded_path, index=False)

    # Ambiguous observations
    ambiguous_df = cleaning_df[
        cleaning_df["eligibility_decision"] == EligibilityDecision.AMBIGUOUS.value
    ].copy()
    ambiguous_path = output_dir / "ambiguous_observations.csv"
    ambiguous_df.to_csv(ambiguous_path, index=False)

    return cleaning_path, excluded_path, ambiguous_path
