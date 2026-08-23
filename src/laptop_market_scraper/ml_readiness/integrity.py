import math
from typing import Any
import pandas as pd

from laptop_market_scraper.ml_readiness.loader import ReadinessDataset
from laptop_market_scraper.ml_readiness.models import IntegrityResult


def _is_valid_price(val: Any) -> bool:
    if pd.isna(val) or val is None or isinstance(val, bool):
        return False
    try:
        fval = float(val)
        return not math.isnan(fval) and fval > 0
    except (ValueError, TypeError):
        return False


def _is_valid_rating(val: Any) -> bool:
    if pd.isna(val) or val is None:
        return True
    if isinstance(val, bool):
        return False
    try:
        fval = float(val)
        return not math.isnan(fval) and 0.0 <= fval <= 5.0
    except (ValueError, TypeError):
        return False


def _is_valid_review_count(val: Any) -> bool:
    if pd.isna(val) or val is None:
        return True
    if isinstance(val, bool):
        return False
    try:
        fval = float(val)
        return not math.isnan(fval) and fval >= 0
    except (ValueError, TypeError):
        return False


def audit_dataset_integrity(
    dataset: ReadinessDataset,
    required_columns: tuple[str, ...] = ("listing_key", "price", "rating", "review_count"),
) -> IntegrityResult:
    """Audit dataset integrity for missing columns, duplicates, numeric range constraints, and orphan records."""
    products_df = dataset.products
    raw_map = dataset.raw_by_listing_key

    normalized_rows = len(products_df)
    raw_rows = len(raw_map)

    # 1. Missing required columns
    missing_required_columns = tuple(col for col in required_columns if col not in products_df.columns)

    # 2. Extract keys & key uniqueness
    raw_keys_set = set(str(k) for k in raw_map.keys())
    unique_raw_keys = len(raw_keys_set)

    duplicate_normalized_keys: tuple[str, ...] = ()
    invalid_price_keys: tuple[str, ...] = ()
    invalid_rating_keys: tuple[str, ...] = ()
    invalid_review_count_keys: tuple[str, ...] = ()
    unique_normalized_keys = 0
    orphan_normalized_records = 0
    orphan_raw_records = 0

    if "listing_key" in products_df.columns:
        norm_keys = [str(x) for x in products_df["listing_key"] if pd.notna(x) and x is not None]
        norm_keys_set = set(norm_keys)
        unique_normalized_keys = len(norm_keys_set)

        # Duplicates
        counts: dict[str, int] = {}
        for k in norm_keys:
            counts[k] = counts.get(k, 0) + 1
        dup_keys = [k for k, count in counts.items() if count > 1]
        duplicate_normalized_keys = tuple(sorted(dup_keys))

        # Orphans
        orphan_normalized_records = len(norm_keys_set - raw_keys_set)
        orphan_raw_records = len(raw_keys_set - norm_keys_set)

        # Value constraints validation
        invalid_price_set: set[str] = set()
        invalid_rating_set: set[str] = set()
        invalid_review_count_set: set[str] = set()

        has_price = "price" in products_df.columns
        has_rating = "rating" in products_df.columns
        has_review_count = "review_count" in products_df.columns

        for _, row in products_df.iterrows():
            lk = str(row["listing_key"]) if pd.notna(row["listing_key"]) else None
            if not lk:
                continue

            if has_price and not _is_valid_price(row["price"]):
                invalid_price_set.add(lk)

            if has_rating and not _is_valid_rating(row["rating"]):
                invalid_rating_set.add(lk)

            if has_review_count and not _is_valid_review_count(row["review_count"]):
                invalid_review_count_set.add(lk)

        invalid_price_keys = tuple(sorted(invalid_price_set))
        invalid_rating_keys = tuple(sorted(invalid_rating_set))
        invalid_review_count_keys = tuple(sorted(invalid_review_count_set))
    else:
        # listing_key missing in products
        orphan_raw_records = unique_raw_keys

    passed = (
        len(missing_required_columns) == 0
        and len(duplicate_normalized_keys) == 0
        and len(invalid_price_keys) == 0
        and len(invalid_rating_keys) == 0
        and len(invalid_review_count_keys) == 0
        and orphan_normalized_records == 0
    )

    return IntegrityResult(
        normalized_rows=normalized_rows,
        raw_rows=raw_rows,
        unique_normalized_keys=unique_normalized_keys,
        unique_raw_keys=unique_raw_keys,
        duplicate_normalized_keys=duplicate_normalized_keys,
        orphan_normalized_records=orphan_normalized_records,
        orphan_raw_records=orphan_raw_records,
        missing_required_columns=missing_required_columns,
        invalid_price_keys=invalid_price_keys,
        invalid_rating_keys=invalid_rating_keys,
        invalid_review_count_keys=invalid_review_count_keys,
        passed=passed,
    )
