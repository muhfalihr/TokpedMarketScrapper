"""Load and reconcile all source data for ML dataset freeze."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from laptop_market_scraper.storage import SQLiteStore


@dataclass(frozen=True)
class MLFreezeInput:
    products: pd.DataFrame
    provenance: pd.DataFrame
    discoveries: pd.DataFrame
    raw_by_listing_key: Mapping[str, dict[str, Any]]
    readiness: dict[str, Any]
    extreme_review: pd.DataFrame
    missingness_review: pd.DataFrame


def _load_raw_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    """Load raw JSONL and index by listing_key."""
    result: dict[str, dict[str, Any]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            key = record.get("listing_key", "")
            if key:
                result[key] = record
    return result


def load_ml_freeze_input(
    *,
    run_id: str,
    store: SQLiteStore,
    raw_jsonl_path: Path,
    readiness_json_path: Path,
    extreme_review_path: Path,
    missingness_review_path: Path,
) -> MLFreezeInput:
    """Load and reconcile all sources needed for ML dataset freeze.

    Raises ValueError on identity mismatches or missing data.
    """
    # Load readiness artifact
    if not readiness_json_path.exists():
        raise FileNotFoundError(f"Readiness artifact not found: {readiness_json_path}")

    with open(readiness_json_path, encoding="utf-8") as f:
        readiness = json.load(f)

    # Load products from SQLite
    products_list = store.read_products_for_run(run_id)
    if not products_list:
        raise ValueError(f"No products found for run_id '{run_id}'")

    products_dicts = [p if isinstance(p, dict) else p.model_dump() for p in products_list]
    products = pd.DataFrame(products_dicts)

    # Validate required columns
    required_cols = {"listing_key", "product_name", "product_url", "price", "rating"}
    missing_cols = required_cols - set(products.columns)
    if missing_cols:
        raise ValueError(f"Missing required product columns: {missing_cols}")

    # Validate listing_key uniqueness
    if not products["listing_key"].is_unique:
        dupes = products["listing_key"][products["listing_key"].duplicated()].tolist()
        raise ValueError(f"Duplicate listing_key values: {dupes}")

    # Load raw JSONL
    if not raw_jsonl_path.exists():
        raise FileNotFoundError(f"Raw JSONL not found: {raw_jsonl_path}")
    raw_by_listing_key = _load_raw_jsonl(raw_jsonl_path)

    # Reconcile identities: normalized products must match raw universe
    normalized_keys = set(products["listing_key"])
    raw_keys = set(raw_by_listing_key)

    if normalized_keys != raw_keys:
        only_normalized = normalized_keys - raw_keys
        only_raw = raw_keys - normalized_keys
        parts = []
        if only_normalized:
            parts.append(f"in normalized but not raw: {sorted(only_normalized)[:5]}")
        if only_raw:
            parts.append(f"in raw but not normalized: {sorted(only_raw)[:5]}")
        raise ValueError(f"Identity mismatch between normalized and raw: {'; '.join(parts)}")

    # Load provenance
    provenance_list = store.read_feature_provenance_for_run(run_id)
    provenance_dicts = [
        p if isinstance(p, dict) else p.model_dump() for p in provenance_list
    ]
    provenance = pd.DataFrame(provenance_dicts) if provenance_dicts else pd.DataFrame()

    # Load discoveries
    discoveries_list = store.read_discoveries_for_run(run_id)
    discoveries = pd.DataFrame(discoveries_list) if discoveries_list else pd.DataFrame()

    # Load review CSVs
    if extreme_review_path.exists() and extreme_review_path.stat().st_size > 0:
        try:
            extreme_review = pd.read_csv(extreme_review_path)
        except pd.errors.EmptyDataError:
            extreme_review = pd.DataFrame()
    else:
        extreme_review = pd.DataFrame()

    if missingness_review_path.exists() and missingness_review_path.stat().st_size > 0:
        try:
            missingness_review = pd.read_csv(missingness_review_path)
        except pd.errors.EmptyDataError:
            missingness_review = pd.DataFrame()
    else:
        missingness_review = pd.DataFrame()

    return MLFreezeInput(
        products=products,
        provenance=provenance,
        discoveries=discoveries,
        raw_by_listing_key=raw_by_listing_key,
        readiness=readiness,
        extreme_review=extreme_review,
        missingness_review=missingness_review,
    )
