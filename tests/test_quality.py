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
