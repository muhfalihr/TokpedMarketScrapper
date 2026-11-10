"""Tests for search discovery storage and provenance tracking."""

from pathlib import Path

import pandas as pd
import pytest

from tokped_market_scrapper.storage import MarketStorage, SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    s = SQLiteStore(tmp_path / "test_discovery.db", data_dir=tmp_path)
    yield s
    s.close()


def test_market_storage_alias():
    assert MarketStorage is SQLiteStore


def test_record_discovery_and_count(store: SQLiteStore):
    assert store.count_discoveries() == 0

    store.record_discovery(
        crawl_run_id="run-1",
        listing_key="pid:100",
        source_query="laptop",
        seed_kind="keyword",
        search_page=1,
        search_start=0,
        search_rows=60,
        search_rank=1,
        category_sc="sc:123",
        sort_code="23",
        observed_total_data=1200,
    )

    assert store.count_discoveries() == 1
    assert store.count_discoveries(listing_key="pid:100") == 1
    assert store.count_discoveries(crawl_run_id="run-1") == 1
    assert store.count_discoveries(listing_key="pid:100", crawl_run_id="run-1") == 1
    assert store.count_discoveries(listing_key="pid:999") == 0
    assert store.count_discoveries(crawl_run_id="run-999") == 0


def test_record_multiple_discoveries_different_queries(store: SQLiteStore):
    store.record_discovery(
        crawl_run_id="run-1",
        listing_key="pid:100",
        source_query="laptop",
        seed_kind="keyword",
        search_page=1,
        search_start=0,
        search_rows=60,
        search_rank=1,
        category_sc="sc:123",
        sort_code="23",
        observed_total_data=1200,
    )

    store.record_discovery(
        crawl_run_id="run-1",
        listing_key="pid:100",
        source_query="laptop asus",
        seed_kind="keyword",
        search_page=1,
        search_start=0,
        search_rows=60,
        search_rank=5,
        category_sc="sc:123",
        sort_code="23",
        observed_total_data=500,
    )

    assert store.count_discoveries(listing_key="pid:100") == 2
    assert store.count_discoveries(crawl_run_id="run-1") == 2


def test_record_duplicate_discovery_ignored(store: SQLiteStore):
    kwargs = {
        "crawl_run_id": "run-1",
        "listing_key": "pid:100",
        "source_query": "laptop",
        "seed_kind": "keyword",
        "search_page": 1,
        "search_start": 0,
        "search_rows": 60,
        "search_rank": 1,
        "category_sc": "sc:123",
        "sort_code": "23",
        "observed_total_data": 1200,
    }

    store.record_discovery(**kwargs)
    store.record_discovery(**kwargs)

    assert store.count_discoveries(listing_key="pid:100") == 1


def test_export_discoveries_csv(store: SQLiteStore, tmp_path: Path):
    store.record_discovery(
        crawl_run_id="run-1",
        listing_key="pid:100",
        source_query="laptop",
        seed_kind="keyword",
        search_page=1,
        search_start=0,
        search_rows=60,
        search_rank=1,
        category_sc="sc:123",
        sort_code="23",
        observed_total_data=1200,
    )
    store.record_discovery(
        crawl_run_id="run-1",
        listing_key="pid:200",
        source_query="laptop lenovo",
        seed_kind="keyword",
        search_page=2,
        search_start=60,
        search_rows=60,
        search_rank=12,
        category_sc="sc:123",
        sort_code="23",
        observed_total_data=800,
    )
    store.record_discovery(
        crawl_run_id="run-2",
        listing_key="pid:300",
        source_query="laptop hp",
        seed_kind="keyword",
        search_page=1,
        search_start=0,
        search_rows=60,
        search_rank=3,
        category_sc="sc:123",
        sort_code="23",
        observed_total_data=300,
    )

    output_csv = tmp_path / "exports" / "discoveries.csv"
    res_path = store.export_discoveries_csv("run-1", output_csv)

    assert res_path == output_csv
    assert output_csv.exists()

    df = pd.read_csv(output_csv)
    assert len(df) == 2
    assert list(df["crawl_run_id"].unique()) == ["run-1"]
    expected_cols = [
        "crawl_run_id",
        "listing_key",
        "source_query",
        "seed_kind",
        "search_page",
        "search_start",
        "search_rows",
        "search_rank",
        "category_sc",
        "sort_code",
        "observed_total_data",
        "product_name",
        "category_breadcrumb",
        "discovered_at",
    ]
    assert list(df.columns) == expected_cols
