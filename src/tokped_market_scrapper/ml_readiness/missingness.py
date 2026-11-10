import math
from typing import Any

import pandas as pd

from laptop_market_scraper.ml_readiness.loader import ReadinessDataset
from laptop_market_scraper.ml_readiness.models import (
    MissingnessCase,
    MissingnessResult,
    MissingSemanticStatus,
)


def _is_missing(val: Any) -> bool:
    if val is None or pd.isna(val):
        return True
    return bool(isinstance(val, float) and math.isnan(val))


def _clean_float(val: Any) -> float | None:
    if _is_missing(val):
        return None
    try:
        fval = float(val)
        if math.isnan(fval):
            return None
        return fval
    except (ValueError, TypeError):
        return None


def _check_raw_for_no_review_state(raw_record: dict[str, Any] | None) -> tuple[bool, bool]:
    """Check raw payload dictionary for explicit no-review indicator or absent review fields.

    Returns:
        (has_explicit_no_review, review_fields_absent)
    """
    if raw_record is None or not isinstance(raw_record, dict):
        return False, True

    dicts_to_check = [raw_record]
    for key in ("product", "stats", "item"):
        sub = raw_record.get(key)
        if isinstance(sub, dict):
            dicts_to_check.append(sub)

    has_rating_field = False
    has_review_field = False
    rating_val = None
    review_val = None

    for d in dicts_to_check:
        for rk, rv in d.items():
            rk_lower = str(rk).lower()
            if "rating" in rk_lower:
                has_rating_field = True
                if rating_val is None and rv is not None:
                    rating_val = rv
            if "review" in rk_lower or "count" in rk_lower:
                has_review_field = True
                if review_val is None and rv is not None:
                    review_val = rv

    if not has_rating_field and not has_review_field:
        return False, True

    def _is_zero(v: Any) -> bool:
        if v is None:
            return False
        if v in (0, 0.0, "0", "0.0", False):
            return True
        try:
            return float(v) == 0.0
        except (ValueError, TypeError):
            return False

    is_rating_zero = _is_zero(rating_val)
    is_review_zero = _is_zero(review_val)

    if is_rating_zero and is_review_zero:
        return True, False
    if is_review_zero and rating_val is None:
        return True, False

    return False, False


def analyze_missingness(dataset: ReadinessDataset) -> MissingnessResult:
    """Analyze joint missingness patterns across rating and review_count, evaluating evidence and semantic status."""
    products_df = dataset.products
    raw_map = dataset.raw_by_listing_key
    provenance_df = dataset.provenance

    total_rows = len(products_df)
    if total_rows == 0:
        return MissingnessResult(
            total_rows=0,
            complete_rating_and_reviews=0,
            missing_rating_only=0,
            missing_reviews_only=0,
            missing_both=0,
            rating_missing_percent=0.0,
            review_missing_percent=0.0,
            median_price_when_review_present=None,
            median_price_when_review_missing=None,
            cases=(),
        )

    has_rating_col = "rating" in products_df.columns
    has_review_col = "review_count" in products_df.columns
    has_price_col = "price" in products_df.columns
    has_key_col = "listing_key" in products_df.columns
    has_name_col = "product_name" in products_df.columns
    has_url_col = "product_url" in products_df.columns

    provenance_keys: set[str] = set()
    if not provenance_df.empty and "listing_key" in provenance_df.columns:
        provenance_keys = {str(k) for k in provenance_df["listing_key"].dropna()}

    complete_rating_and_reviews = 0
    missing_rating_only = 0
    missing_reviews_only = 0
    missing_both = 0
    rating_missing_count = 0
    review_missing_count = 0

    prices_review_present: list[float] = []
    prices_review_missing: list[float] = []

    cases: list[MissingnessCase] = []

    for _, row in products_df.iterrows():
        listing_key = str(row["listing_key"]) if has_key_col and pd.notna(row["listing_key"]) else ""
        product_name = str(row["product_name"]) if has_name_col and pd.notna(row["product_name"]) else None
        product_url = str(row["product_url"]) if has_url_col and pd.notna(row["product_url"]) else None

        raw_rating = row["rating"] if has_rating_col else None
        raw_review_count = row["review_count"] if has_review_col else None
        raw_price = row["price"] if has_price_col else None

        rating = _clean_float(raw_rating)
        review_count = _clean_float(raw_review_count)
        price = _clean_float(raw_price)

        rating_missing = rating is None
        review_count_missing = review_count is None

        if rating_missing:
            rating_missing_count += 1
        if review_count_missing:
            review_missing_count += 1

        if price is not None and price > 0:
            if review_count_missing:
                prices_review_missing.append(price)
            else:
                prices_review_present.append(price)

        if not rating_missing and not review_count_missing:
            complete_rating_and_reviews += 1
            continue

        if rating_missing and not review_count_missing:
            missing_rating_only += 1
        elif not rating_missing and review_count_missing:
            missing_reviews_only += 1
        else:
            missing_both += 1

        evidence: list[str] = []
        if rating_missing:
            evidence.append("rating_missing")
        if review_count_missing:
            evidence.append("review_count_missing")

        if rating_missing and review_count_missing:
            evidence.append("both_rating_and_review_missing")
        elif not rating_missing and review_count_missing:
            evidence.append("rating_present_review_missing")
        elif rating_missing and not review_count_missing:
            evidence.append("review_present_rating_missing")

        if provenance_df.empty or (listing_key and listing_key not in provenance_keys):
            evidence.append("provenance_missing")

        raw_record = raw_map.get(listing_key)
        if raw_record is None:
            evidence.append("raw_record_missing")
            has_no_review_state, review_fields_absent = False, True
        else:
            has_no_review_state, review_fields_absent = _check_raw_for_no_review_state(raw_record)
            if has_no_review_state:
                evidence.append("review_count_zero_explicit")
                evidence.append("explicit_no_review_state_in_raw")
            elif review_fields_absent:
                evidence.append("raw_review_field_absent")

        if rating_missing and review_count_missing:
            if has_no_review_state:
                semantic_status = MissingSemanticStatus.SUPPORTED
            elif review_fields_absent:
                semantic_status = MissingSemanticStatus.LIKELY
            else:
                semantic_status = MissingSemanticStatus.UNRESOLVED
        elif not rating_missing and review_count_missing:
            semantic_status = MissingSemanticStatus.UNRESOLVED
        elif rating_missing and not review_count_missing:
            semantic_status = MissingSemanticStatus.AMBIGUOUS
        else:
            semantic_status = MissingSemanticStatus.UNRESOLVED

        cases.append(
            MissingnessCase(
                listing_key=listing_key,
                product_name=product_name,
                product_url=product_url,
                rating=rating,
                review_count=review_count,
                rating_missing=rating_missing,
                review_count_missing=review_count_missing,
                semantic_status=semantic_status,
                evidence=tuple(evidence),
            )
        )

    rating_missing_percent = (rating_missing_count / total_rows) * 100.0
    review_missing_percent = (review_missing_count / total_rows) * 100.0

    median_price_when_review_present = (
        float(pd.Series(prices_review_present).median()) if prices_review_present else None
    )
    median_price_when_review_missing = (
        float(pd.Series(prices_review_missing).median()) if prices_review_missing else None
    )

    return MissingnessResult(
        total_rows=total_rows,
        complete_rating_and_reviews=complete_rating_and_reviews,
        missing_rating_only=missing_rating_only,
        missing_reviews_only=missing_reviews_only,
        missing_both=missing_both,
        rating_missing_percent=rating_missing_percent,
        review_missing_percent=review_missing_percent,
        median_price_when_review_present=median_price_when_review_present,
        median_price_when_review_missing=median_price_when_review_missing,
        cases=tuple(cases),
    )


audit_missingness = analyze_missingness
