"""Dataset quality report and reproducibility manifest generation."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tokped_market_scrapper.eligibility import (
    _extract_breadcrumb_and_name,
    evaluate_laptop_eligibility,
)
from tokped_market_scrapper.storage import SQLiteStore


class QualityReport(BaseModel):
    row_count: int
    duplicate_count: int
    rejected_count: int
    coverage_product_name: float
    coverage_price: float
    coverage_sold_count: float
    coverage_rating: float
    coverage_review_count: float
    invalid_rating_count: int
    invalid_discount_count: int
    price_min: int | None
    price_median: float | None
    price_max: int | None
    invalid_numeric_count: int
    invalid_eligibility_count: int
    research_ready: bool

    search_pages_fetched: int = 0
    search_results_seen: int = 0
    eligible_laptop_count: int = 0
    rejected_non_laptop_count: int = 0
    eligibility_rate: float = 0.0
    duplicate_discovery_count: int = 0
    unique_listing_count: int = 0
    eligibility_rate_by_query: dict[str, float] = Field(default_factory=dict)
    accepted_count_by_query: dict[str, int] = Field(default_factory=dict)
    rejected_count_by_query: dict[str, int] = Field(default_factory=dict)
    accepted_count_by_breadcrumb: dict[str, int] = Field(default_factory=dict)
    rejected_count_by_breadcrumb: dict[str, int] = Field(default_factory=dict)
    observed_total_data_min: int | None = None
    observed_total_data_max: int | None = None


def generate_quality_report(
    discoveries: list[dict | Any] | None = None,
    store: SQLiteStore | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate search acquisition quality metrics across search discoveries."""
    if discoveries is None:
        discoveries = []
        if store and hasattr(store, "get_discoveries"):
            discoveries = store.get_discoveries(run_id=run_id)

    pages_seen: set[tuple[str, int]] = set()
    seen_listing_keys: set[str] = set()
    observed_total_data_values: list[int] = []

    eligible_laptop_count = 0
    rejected_non_laptop_count = 0

    accepted_count_by_query: dict[str, int] = defaultdict(int)
    rejected_count_by_query: dict[str, int] = defaultdict(int)
    accepted_count_by_breadcrumb: dict[str, int] = defaultdict(int)
    rejected_count_by_breadcrumb: dict[str, int] = defaultdict(int)

    for item in discoveries:
        if isinstance(item, dict):
            query = item.get("source_query") or item.get("query") or "unknown"
            page = item.get("search_page") or item.get("page") or 1
            total_data = item.get("observed_total_data") if "observed_total_data" in item else item.get("total_data")
            listing_key = item.get("listing_key") or item.get("product_id") or item.get("url") or ""
        else:
            query = getattr(item, "source_query", getattr(item, "query", "unknown"))
            page = getattr(item, "search_page", getattr(item, "page", 1))
            total_data = getattr(item, "observed_total_data", getattr(item, "total_data", None))
            listing_key = getattr(item, "listing_key", getattr(item, "product_id", getattr(item, "url", "")))

        query = str(query)
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1

        pages_seen.add((query, page))

        if total_data is not None:
            try:
                observed_total_data_values.append(int(total_data))
            except (ValueError, TypeError):
                pass

        if listing_key:
            seen_listing_keys.add(str(listing_key))

        breadcrumb, _ = _extract_breadcrumb_and_name(item)

        if isinstance(item, dict) and "accepted" in item:
            accepted = bool(item["accepted"])
        elif hasattr(item, "accepted") and isinstance(item.accepted, bool):
            accepted = bool(item.accepted)
        else:
            accepted = evaluate_laptop_eligibility(item).accepted

        if accepted:
            eligible_laptop_count += 1
            accepted_count_by_query[query] += 1
            accepted_count_by_breadcrumb[breadcrumb] += 1
        else:
            rejected_non_laptop_count += 1
            rejected_count_by_query[query] += 1
            rejected_count_by_breadcrumb[breadcrumb] += 1

    search_results_seen = len(discoveries)
    search_pages_fetched = len(pages_seen)
    unique_listing_count = len(seen_listing_keys)
    duplicate_discovery_count = max(0, search_results_seen - unique_listing_count)

    eligibility_rate = (
        eligible_laptop_count / search_results_seen if search_results_seen > 0 else 0.0
    )

    all_queries = set(accepted_count_by_query.keys()) | set(rejected_count_by_query.keys())
    eligibility_rate_by_query: dict[str, float] = {}
    for q in all_queries:
        acc = accepted_count_by_query.get(q, 0)
        rej = rejected_count_by_query.get(q, 0)
        tot = acc + rej
        eligibility_rate_by_query[q] = acc / tot if tot > 0 else 0.0

    observed_total_data_min = min(observed_total_data_values) if observed_total_data_values else None
    observed_total_data_max = max(observed_total_data_values) if observed_total_data_values else None

    out_dict = {}
    if store and run_id:
        coverage_report = build_quality_report(run_id, store)
        out_dict.update(coverage_report.model_dump())

    out_dict.update(
        {
            "search_pages_fetched": search_pages_fetched,
            "search_results_seen": search_results_seen,
            "eligible_laptop_count": eligible_laptop_count,
            "rejected_non_laptop_count": rejected_non_laptop_count,
            "eligibility_rate": eligibility_rate,
            "duplicate_discovery_count": duplicate_discovery_count,
            "unique_listing_count": unique_listing_count,
            "eligibility_rate_by_query": dict(eligibility_rate_by_query),
            "accepted_count_by_query": dict(accepted_count_by_query),
            "rejected_count_by_query": dict(rejected_count_by_query),
            "accepted_count_by_breadcrumb": dict(accepted_count_by_breadcrumb),
            "rejected_count_by_breadcrumb": dict(rejected_count_by_breadcrumb),
            "observed_total_data_min": observed_total_data_min,
            "observed_total_data_max": observed_total_data_max,
        }
    )

    return out_dict


def export_quality_report(crawl_dir: Path | str, data: dict[str, Any]) -> Path:
    """Save quality report dictionary as quality.json in crawl_dir."""
    out_dir = Path(crawl_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "quality.json"
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return json_path


def build_quality_report(run_id: str, store: SQLiteStore) -> QualityReport:
    """Generate a quality report for a given crawl run."""
    products = store.get_all_products(run_id=run_id)
    rejected_count = store.count_rejected(run_id=run_id)

    row_count = len(products)

    if row_count == 0:
        return QualityReport(
            row_count=0,
            duplicate_count=0,
            rejected_count=rejected_count,
            coverage_product_name=0.0,
            coverage_price=0.0,
            coverage_sold_count=0.0,
            coverage_rating=0.0,
            coverage_review_count=0.0,
            invalid_rating_count=0,
            invalid_discount_count=0,
            price_min=None,
            price_median=None,
            price_max=None,
            invalid_numeric_count=0,
            invalid_eligibility_count=0,
            research_ready=False,
        )

    duplicate_count = 0
    invalid_numeric_count = 0
    invalid_eligibility_count = 0
    invalid_rating_count = 0
    invalid_discount_count = 0

    product_names = 0
    prices = []
    sold_counts = 0
    ratings = 0
    review_counts = 0

    for p in products:
        if p.product_name:
            product_names += 1
        if p.price is not None:
            prices.append(p.price)
        if p.sold_count is not None:
            sold_counts += 1
        if p.rating is not None:
            ratings += 1
            if p.rating < 0 or p.rating > 5:
                invalid_rating_count += 1
        if p.review_count is not None:
            review_counts += 1
        if p.discount_percent is not None and (p.discount_percent < 0 or p.discount_percent > 100):
            invalid_discount_count += 1

    coverage_product_name = product_names / row_count
    coverage_price = len(prices) / row_count
    coverage_sold_count = sold_counts / row_count
    coverage_rating = ratings / row_count
    coverage_review_count = review_counts / row_count

    prices.sort()
    price_min = prices[0] if prices else None
    price_max = prices[-1] if prices else None

    if prices:
        mid = len(prices) // 2
        if len(prices) % 2 == 0:
            price_median = (prices[mid - 1] + prices[mid]) / 2.0
        else:
            price_median = float(prices[mid])
    else:
        price_median = None

    research_ready = (
        duplicate_count == 0
        and invalid_numeric_count == 0
        and coverage_product_name >= 0.99
        and coverage_price >= 0.95
        and invalid_eligibility_count == 0
    )

    return QualityReport(
        row_count=row_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
        coverage_product_name=coverage_product_name,
        coverage_price=coverage_price,
        coverage_sold_count=coverage_sold_count,
        coverage_rating=coverage_rating,
        coverage_review_count=coverage_review_count,
        invalid_rating_count=invalid_rating_count,
        invalid_discount_count=invalid_discount_count,
        price_min=price_min,
        price_median=price_median,
        price_max=price_max,
        invalid_numeric_count=invalid_numeric_count,
        invalid_eligibility_count=invalid_eligibility_count,
        research_ready=research_ready,
    )
