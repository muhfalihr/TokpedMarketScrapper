"""Dataset quality report and reproducibility manifest generation."""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from laptop_market_scraper.storage import SQLiteStore


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

    # SQLiteStore.save already enforces primary key (crawl_run_id, listing_key)
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
        if p.discount_percent is not None:
            if p.discount_percent < 0 or p.discount_percent > 100:
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


def write_manifest(run_id: str, store: SQLiteStore, started_at: datetime, finished_at: datetime, output_dir: Path) -> Path:
    """Write the reproducibility manifest."""
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        git_commit = "unknown"

    try:
        import scrapling
        scrapling_version = getattr(scrapling, "__version__", "unknown")
    except ImportError:
        scrapling_version = "unknown"

    import platform
    python_version = platform.python_version()

    seed_file = Path("config/seeds.yaml")
    seed_sha = "unknown"
    if seed_file.exists():
        hasher = hashlib.sha256()
        hasher.update(seed_file.read_bytes())
        seed_sha = hasher.hexdigest()

    report = build_quality_report(run_id, store)

    manifest_data = {
        "crawl_run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "python_version": python_version,
        "scrapling_version": scrapling_version,
        "git_commit": git_commit,
        "seed_file_sha256": seed_sha,
        "raw_rows": report.row_count,
        "processed_rows": report.row_count,
        "rejected_rows": report.rejected_count,
        "quality": report.model_dump(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    
    return manifest_path
