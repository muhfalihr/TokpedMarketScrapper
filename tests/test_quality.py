"""Tests for the quality report and reproducibility manifest."""

from datetime import UTC, datetime

import pytest

from laptop_market_scraper.models import NormalizedProduct
from laptop_market_scraper.quality import build_quality_report
from laptop_market_scraper.storage import SQLiteStore


@pytest.fixture
def populated_store(tmp_path):
    store = SQLiteStore(tmp_path / "test.db", data_dir=tmp_path)
    # Add a valid product
    store.save(
        NormalizedProduct(
            crawl_run_id="run-1",
            scraped_at=datetime.now(UTC),
            product_name="ASUS Vivobook",
            product_url="https://example.com/p1",
            canonical_url="https://example.com/p1",
            listing_key="pid:1",
            price=10_000_000,
        )
    )
    # Add another valid product
    store.save(
        NormalizedProduct(
            crawl_run_id="run-1",
            scraped_at=datetime.now(UTC),
            product_name="Lenovo LOQ",
            product_url="https://example.com/p2",
            canonical_url="https://example.com/p2",
            listing_key="pid:2",
            price=15_000_000,
            rating=4.5,
            sold_count=100,
        )
    )
    yield store
    store.close()


def test_quality_report_detects_duplicate_free_dataset(populated_store):
    report = build_quality_report("run-1", populated_store)

    assert report.duplicate_count == 0
    assert report.invalid_rating_count == 0
    assert report.invalid_discount_count == 0


def test_quality_report_computes_price_coverage(populated_store):
    report = build_quality_report("run-1", populated_store)

    assert 0.0 <= report.coverage_price <= 1.0
    assert report.coverage_price == 1.0
    assert report.research_ready is True


def test_generate_quality_report_aggregates_search_metrics():
    from laptop_market_scraper.quality import generate_quality_report

    mock_discoveries = [
        {
            "source_query": "laptop asus",
            "search_page": 1,
            "product_name": "ASUS Vivobook 15",
            "category": {"breadcrumb": "komputer-laptop/laptop/consumer-laptop"},
            "listing_key": "pid:1",
            "observed_total_data": 100,
        },
        {
            "source_query": "laptop asus",
            "search_page": 1,
            "product_name": "Tas Laptop ASUS",
            "category": {"breadcrumb": "komputer-laptop/aksesoris-laptop"},
            "listing_key": "pid:2",
            "observed_total_data": 100,
        },
        {
            "source_query": "laptop lenovo",
            "search_page": 1,
            "product_name": "Lenovo IdeaPad",
            "category": {"breadcrumb": "komputer-laptop/laptop/consumer-laptop"},
            "listing_key": "pid:1",
            "observed_total_data": 50,
        },
    ]

    report = generate_quality_report(discoveries=mock_discoveries)

    assert report["search_pages_fetched"] == 2
    assert report["search_results_seen"] == 3
    assert report["eligible_laptop_count"] == 2
    assert report["rejected_non_laptop_count"] == 1
    assert report["eligibility_rate"] == pytest.approx(2 / 3)
    assert report["unique_listing_count"] == 2
    assert report["duplicate_discovery_count"] == 1
    assert report["accepted_count_by_query"]["laptop asus"] == 1
    assert report["accepted_count_by_query"]["laptop lenovo"] == 1
    assert report["rejected_count_by_query"]["laptop asus"] == 1
    assert report["rejected_count_by_query"].get("laptop lenovo", 0) == 0
    assert report["eligibility_rate_by_query"]["laptop asus"] == 0.5
    assert report["eligibility_rate_by_query"]["laptop lenovo"] == 1.0
    assert report["accepted_count_by_breadcrumb"]["komputer-laptop/laptop/consumer-laptop"] == 2
    assert report["rejected_count_by_breadcrumb"]["komputer-laptop/aksesoris-laptop"] == 1
    assert report["observed_total_data_min"] == 50
    assert report["observed_total_data_max"] == 100


def test_export_quality_report(tmp_path):
    import json

    from laptop_market_scraper.quality import export_quality_report

    data = {"search_pages_fetched": 5, "eligibility_rate": 0.8}
    out_path = export_quality_report(tmp_path, data)

    assert out_path == tmp_path / "quality.json"
    assert out_path.exists()
    assert json.loads(out_path.read_text(encoding="utf-8")) == data

