"""Tests for ML freeze loader module (Task 2)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from laptop_market_scraper.ml_freeze.loader import load_ml_freeze_input
from laptop_market_scraper.models import NormalizedProduct
from laptop_market_scraper.storage import SQLiteStore


@pytest.fixture
def freeze_sources(tmp_path: Path):
    run_id = "test-run-1"

    # 1. Setup SQLite database
    db_path = tmp_path / "crawl.sqlite3"
    store = SQLiteStore(db_path, data_dir=tmp_path)

    products = [
        NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at="2026-08-23T00:00:00Z",
            product_name="Laptop A",
            product_url="https://tokopedia.com/a",
            canonical_url="https://tokopedia.com/a",
            listing_key="key-a",
            price=10_000_000,
            rating=4.5,
            review_count=10,
        ),
        NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at="2026-08-23T00:00:00Z",
            product_name="Laptop B",
            product_url="https://tokopedia.com/b",
            canonical_url="https://tokopedia.com/b",
            listing_key="key-b",
            price=20_000_000,
            rating=5.0,
            review_count=None,
        ),
    ]
    raw_payloads = [
        {"listing_key": "key-a", "product_name_raw": "Laptop A", "price_raw": "10000000"},
        {"listing_key": "key-b", "product_name_raw": "Laptop B", "price_raw": "20000000"},
    ]
    for p in products:
        store.save(p)

    # 2. Raw JSONL file
    raw_jsonl_path = tmp_path / "products.jsonl"
    with open(raw_jsonl_path, "w", encoding="utf-8") as f:
        for p in raw_payloads:
            f.write(json.dumps(p) + "\n")

    # 3. Readiness JSON file
    readiness_path = tmp_path / "ml_readiness.json"
    readiness_data = {"run_id": run_id, "dataset_rows": 2}
    with open(readiness_path, "w", encoding="utf-8") as f:
        json.dump(readiness_data, f)

    # 4. CSV files
    extreme_path = tmp_path / "extreme_price_review.csv"
    pd.DataFrame([{"listing_key": "key-a"}]).to_csv(extreme_path, index=False)

    missingness_path = tmp_path / "missingness_cases.csv"
    pd.DataFrame([{"listing_key": "key-b"}]).to_csv(missingness_path, index=False)

    return {
        "run_id": run_id,
        "store": store,
        "raw_jsonl_path": raw_jsonl_path,
        "readiness_json_path": readiness_path,
        "extreme_review_path": extreme_path,
        "missingness_review_path": missingness_path,
    }


def test_freeze_loader_loads_matching_universe(freeze_sources):
    data = load_ml_freeze_input(**freeze_sources)

    assert data.products["listing_key"].is_unique
    assert set(data.products["listing_key"]) == set(data.raw_by_listing_key.keys())
    assert len(data.products) == 2


def test_freeze_loader_rejects_missing_readiness_file(freeze_sources):
    freeze_sources["readiness_json_path"] = Path("nonexistent.json")
    with pytest.raises(FileNotFoundError):
        load_ml_freeze_input(**freeze_sources)


def test_freeze_loader_rejects_raw_jsonl_identity_mismatch(freeze_sources, tmp_path):
    # Overwrite raw JSONL with different listing keys
    mismatched_raw = tmp_path / "mismatched.jsonl"
    with open(mismatched_raw, "w", encoding="utf-8") as f:
        f.write(json.dumps({"listing_key": "different-key"}) + "\n")

    freeze_sources["raw_jsonl_path"] = mismatched_raw
    with pytest.raises(ValueError, match="Identity mismatch"):
        load_ml_freeze_input(**freeze_sources)
