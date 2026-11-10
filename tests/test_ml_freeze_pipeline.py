"""Tests for end-to-end ML freeze pipeline and artifact rendering (Tasks 9 & 11)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from laptop_market_scraper.ml_freeze.freeze import freeze_ml_dataset
from laptop_market_scraper.models import NormalizedProduct
from laptop_market_scraper.storage import SQLiteStore


@pytest.fixture
def freeze_env(tmp_path: Path):
    run_id = "run-freeze-test"

    # SQLite
    db_path = tmp_path / "crawl.sqlite3"
    store = SQLiteStore(db_path, data_dir=tmp_path)

    products = [
        NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at="2026-08-23T00:00:00Z",
            product_name="ASUS ROG Strix Gaming Laptop",
            product_url="https://tokopedia.com/asus-rog",
            canonical_url="https://tokopedia.com/asus-rog",
            listing_key="rog-1",
            price=25_000_000,
            rating=4.9,
            review_count=50,
        ),
        NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at="2026-08-23T00:00:00Z",
            product_name="LCD LED HP Ultrabook 14-B HD",
            product_url="https://tokopedia.com/lcd-hp",
            canonical_url="https://tokopedia.com/lcd-hp",
            listing_key="lcd-1",
            price=850_000,
            rating=4.2,
            review_count=5,
        ),
        NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at="2026-08-23T00:00:00Z",
            product_name="Lenovo ThinkPad X1 Carbon",
            product_url="https://tokopedia.com/thinkpad-x1",
            canonical_url="https://tokopedia.com/thinkpad-x1",
            listing_key="x1-1",
            price=18_000_000,
            rating=5.0,
            review_count=None,
        ),
    ]

    raw_payloads = [
        {
            "listing_key": "rog-1",
            "product_name_raw": "ASUS ROG Strix Gaming Laptop",
            "price_raw": "25000000",
        },
        {
            "listing_key": "lcd-1",
            "product_name_raw": "LCD LED HP Ultrabook 14-B HD",
            "price_raw": "850000",
        },
        {
            "listing_key": "x1-1",
            "product_name_raw": "Lenovo ThinkPad X1 Carbon",
            "price_raw": "18000000",
        },
    ]

    for p in products:
        store.save(p)

    # Raw JSONL
    raw_jsonl_path = tmp_path / "products.jsonl"
    with open(raw_jsonl_path, "w", encoding="utf-8") as f:
        for p in raw_payloads:
            f.write(json.dumps(p) + "\n")

    # Readiness JSON
    readiness_path = tmp_path / "ml_readiness.json"
    with open(readiness_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "dataset_rows": 3}, f)

    extreme_path = tmp_path / "extreme_price_review.csv"
    pd.DataFrame([]).to_csv(extreme_path, index=False)

    missingness_path = tmp_path / "missingness_cases.csv"
    pd.DataFrame([]).to_csv(missingness_path, index=False)

    return {
        "run_id": run_id,
        "config_path": Path("config/ml_freeze.yaml"),
        "store": store,
        "raw_jsonl_path": raw_jsonl_path,
        "readiness_json_path": readiness_path,
        "extreme_review_path": extreme_path,
        "missingness_review_path": missingness_path,
        "output_dir": tmp_path / "output",
    }


def test_freeze_pipeline_outputs_all_required_files(freeze_env):
    result = freeze_ml_dataset(**freeze_env)

    expected = {
        "r1_price_rating.parquet",
        "r2_price_rating_review_count.parquet",
        "cleaning_decisions.csv",
        "excluded_observations.csv",
        "ambiguous_observations.csv",
        "ml_dataset_manifest.json",
        "README.md",
    }

    actual = {
        p.name
        for p in [
            result.r1_path,
            result.r2_path,
            result.cleaning_decisions_path,
            result.excluded_observations_path,
            result.ambiguous_observations_path,
            result.manifest_path,
            result.readme_path,
        ]
    }

    assert expected == actual


def test_cleaning_artifacts_preserve_all_source_decisions(freeze_env):
    result = freeze_ml_dataset(**freeze_env)

    cleaning = pd.read_csv(result.cleaning_decisions_path)
    assert len(cleaning) == result.source_row_count
    assert len(cleaning) == 3


def test_freeze_excludes_lcd_panel(freeze_env):
    result = freeze_ml_dataset(**freeze_env)

    r1 = pd.read_parquet(result.r1_path)
    r2 = pd.read_parquet(result.r2_path)

    # LCD panel (lcd-1) must be excluded from both
    assert "lcd-1" not in r1["listing_key"].values
    assert "lcd-1" not in r2["listing_key"].values

    # ROG laptop (rog-1) in both
    assert "rog-1" in r1["listing_key"].values
    assert "rog-1" in r2["listing_key"].values

    # ThinkPad X1 (x1-1) in R1, but not R2 (missing review_count)
    assert "x1-1" in r1["listing_key"].values
    assert "x1-1" not in r2["listing_key"].values


def test_finalization_does_not_change_representation_contracts():
    from laptop_market_scraper.ml_freeze.config import load_ml_freeze_config

    config = load_ml_freeze_config("config/ml_freeze.yaml")
    assert config.representations["R1"].features == ("price", "rating")
    assert config.representations["R2"].features == ("price", "rating", "review_count")


def test_v1_0_1_to_v1_0_2_diff_has_correct_net_exclusion_change():
    from laptop_market_scraper.ml_freeze.render import build_decision_diff

    baseline_v1_0_1_df = pd.read_csv("tests/fixtures/ml_freeze/baseline_v1_0_1_decisions.csv")
    current_v1_0_2_df = pd.read_csv("data/ml/smoke-250/ml-dataset-v1.0.2/cleaning_decisions.csv")

    diff = build_decision_diff(
        previous_decisions=baseline_v1_0_1_df,
        current_decisions=current_v1_0_2_df,
        previous_artifact="ml-dataset-v1.0.1",
        current_artifact="ml-dataset-v1.0.2",
    )

    counts = diff["change_type"].value_counts()
    valid_to_exclude = int(counts.get("VALID_TO_EXCLUDE", 0))
    exclude_to_valid = int(counts.get("EXCLUDE_TO_VALID", 0))

    assert valid_to_exclude - exclude_to_valid == 41


