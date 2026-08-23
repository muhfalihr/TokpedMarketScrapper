"""Render cleaning evidence artifacts (CSVs) for ML dataset freeze."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from laptop_market_scraper.ml_freeze.models import CleaningDecision, EligibilityDecision
from laptop_market_scraper.ml_freeze.review_semantics import ReviewCountResolution


def build_decision_diff(
    *,
    previous_decisions: pd.DataFrame,
    current_decisions: pd.DataFrame,
) -> pd.DataFrame:
    """Build a deterministic before/after decision diff DataFrame.

    Required columns:
    listing_key, product_name, previous_decision, previous_reason,
    current_decision, current_reason, changed, change_type
    """
    prev_map = {row["listing_key"]: row for _, row in previous_decisions.iterrows()}

    diff_records = []
    for _, curr in current_decisions.iterrows():
        key = curr["listing_key"]
        prev = prev_map.get(key, {})

        prev_dec = str(prev.get("eligibility_decision", "UNKNOWN"))
        prev_rea = str(prev.get("eligibility_reason", "UNKNOWN"))
        curr_dec = str(curr.get("eligibility_decision", ""))
        curr_rea = str(curr.get("eligibility_reason", ""))
        prod_name = str(curr.get("product_name", prev.get("product_name", "")))

        if prev_dec == "EXCLUDE" and curr_dec == "VALID_LAPTOP":
            change_type = "EXCLUDE_TO_VALID"
            changed = True
        elif prev_dec == "VALID_LAPTOP" and curr_dec == "EXCLUDE":
            change_type = "VALID_TO_EXCLUDE"
            changed = True
        elif prev_dec != curr_dec:
            change_type = "DECISION_CHANGED"
            changed = True
        elif prev_rea != curr_rea:
            change_type = "REASON_CHANGED"
            changed = True
        else:
            change_type = "UNCHANGED"
            changed = False

        diff_records.append({
            "listing_key": key,
            "product_name": prod_name,
            "previous_decision": prev_dec,
            "previous_reason": prev_rea,
            "current_decision": curr_dec,
            "current_reason": curr_rea,
            "changed": changed,
            "change_type": change_type,
        })

    diff_df = pd.DataFrame(diff_records)
    if not diff_df.empty:
        diff_df = diff_df.sort_values(
            by=["changed", "change_type", "listing_key"],
            ascending=[False, True, True],
        ).reset_index(drop=True)

    return diff_df


def build_low_price_review(
    *,
    products: pd.DataFrame,
    decisions: Sequence[CleaningDecision],
    threshold: int = 2_000_000,
) -> pd.DataFrame:
    """Build diagnostic review queue of valid laptops with price below threshold.

    Diagnostic only — never alters eligibility decisions directly.
    """
    dec_map = {d.listing_key: d for d in decisions}

    records = []
    for _, row in products.iterrows():
        key = row["listing_key"]
        price = row.get("price")
        d = dec_map.get(key)
        if not d or d.eligibility_decision != EligibilityDecision.VALID_LAPTOP:
            continue

        if price is not None and pd.notna(price) and price < threshold:
            records.append({
                "listing_key": key,
                "product_name": row.get("product_name", ""),
                "product_url": row.get("product_url", ""),
                "price": price,
                "eligibility_decision": d.eligibility_decision.value,
                "eligibility_reason": d.eligibility_reason.value,
                "review_status": "PENDING_REVIEW",
                "review_note": f"Price {price} is below diagnostic threshold {threshold}",
            })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(by=["price", "listing_key"], ascending=[True, True]).reset_index(drop=True)
    return df


def write_cleaning_artifacts(
    *,
    decisions: Sequence[CleaningDecision],
    review_resolutions: dict[str, ReviewCountResolution],
    products: pd.DataFrame,
    output_dir: Path,
    previous_cleaning_decisions_path: Path | None = None,
    low_price_threshold: int = 2_000_000,
) -> tuple[Path, Path, Path, Path | None, Path]:
    """Write cleaning_decisions.csv, excluded_observations.csv, ambiguous_observations.csv, decision_diff.csv, low_price_review.csv.

    Returns paths to the written CSV files.
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

    # Low-price review queue
    low_price_df = build_low_price_review(
        products=products,
        decisions=decisions,
        threshold=low_price_threshold,
    )
    low_price_path = output_dir / "low_price_review.csv"
    low_price_df.to_csv(low_price_path, index=False)

    # Optional decision diff
    diff_path: Path | None = None
    if (
        previous_cleaning_decisions_path
        and previous_cleaning_decisions_path.exists()
        and previous_cleaning_decisions_path.stat().st_size > 0
    ):
        prev_df = pd.read_csv(previous_cleaning_decisions_path)
        diff_df = build_decision_diff(
            previous_decisions=prev_df,
            current_decisions=cleaning_df,
        )
        diff_path = output_dir / "decision_diff.csv"
        diff_df.to_csv(diff_path, index=False)

    return cleaning_path, excluded_path, ambiguous_path, diff_path, low_price_path
