"""Tests for the storage module."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from tokped_market_scrapper.models import NormalizedProduct
from tokped_market_scrapper.storage import SQLiteStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "test.db", data_dir=tmp_path)
    yield s
    s.close()


def _make_product(
    crawl_run_id: str = "run-1",
    listing_key: str = "pid:12345",
    **kwargs,
) -> NormalizedProduct:
    defaults = {
        "crawl_run_id": crawl_run_id,
        "scraped_at": datetime.now(UTC),
        "product_name": "ASUS Vivobook 14",
        "product_url": "https://www.tokopedia.com/shop/product",
        "canonical_url": "https://www.tokopedia.com/shop/product",
        "listing_key": listing_key,
        "price": 10_000_000,
    }
    defaults.update(kwargs)
    return NormalizedProduct(**defaults)


@pytest.fixture
def normalized_product():
    return _make_product()


@pytest.fixture
def product_factory():
    return _make_product


def test_same_listing_saved_once_per_run(store, normalized_product):
    assert store.save(normalized_product) is True
    assert store.save(normalized_product) is False
    assert store.count_products() == 1


def test_same_listing_can_exist_in_different_runs(store, product_factory):
    store.save(product_factory(crawl_run_id="run-a"))
    store.save(product_factory(crawl_run_id="run-b"))

    assert store.count_products() == 2


def test_export_creates_csv_and_parquet(store, normalized_product, tmp_path):
    store.save(normalized_product)

    csv_path = tmp_path / "out" / "laptops.csv"
    parquet_path = tmp_path / "out" / "laptops.parquet"

    store.export_processed(csv_path, parquet_path)

    assert csv_path.exists()
    assert parquet_path.exists()

    df_csv = pd.read_csv(csv_path)
    assert len(df_csv) == 1
    assert df_csv["product_name"].iloc[0] == "ASUS Vivobook 14"

    df_pq = pd.read_parquet(parquet_path)
    assert len(df_pq) == 1


def test_raw_jsonl_written(store, normalized_product, tmp_path):
    store.save(normalized_product)

    jsonl_path = tmp_path / "raw" / "run-1" / "products.jsonl"
    assert jsonl_path.exists()
    assert jsonl_path.read_text(encoding="utf-8").strip() != ""
