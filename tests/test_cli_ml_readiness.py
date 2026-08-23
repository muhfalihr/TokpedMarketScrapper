"""Tests for the audit-ml-readiness CLI command."""

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from laptop_market_scraper.cli import app
from laptop_market_scraper.models import NormalizedProduct
from laptop_market_scraper.storage import SQLiteStore

runner = CliRunner()


def test_audit_ml_readiness_help():
    result = runner.invoke(app, ["audit-ml-readiness", "--help"])
    assert result.exit_code == 0
    assert "--run-id" in result.stdout
    assert "--config" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--crawl-dir" in result.stdout
    assert "--strict" in result.stdout
    assert "--sample-extremes" in result.stdout


def test_audit_ml_readiness_strict_fail(tmp_path: Path):
    run_id = "test-run-strict-ml"
    crawl_dir = tmp_path / "crawl_state"
    crawl_dir.mkdir(parents=True)
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    now = datetime.now(UTC)
    # Save a product with orphan key (no raw jsonl record)
    product = NormalizedProduct(
        crawl_run_id=run_id,
        scraped_at=now,
        product_name="Laptop Strict Test",
        product_url="https://tokopedia.com/product-strict",
        canonical_url="https://tokopedia.com/product-strict",
        listing_key="key-strict-orphan",
        price=10000000,
    )
    store.save(product)

    # Empty raw dir so orphan_normalized_records > 0 or missing_raw_counterparts
    run_raw_dir = crawl_dir / run_id
    run_raw_dir.mkdir(parents=True)
    (run_raw_dir / "products.jsonl").write_text("", encoding="utf-8")

    out_dir = tmp_path / "reports_strict"

    result = runner.invoke(
        app,
        [
            "audit-ml-readiness",
            "--run-id",
            run_id,
            "--crawl-dir",
            str(crawl_dir),
            "--output-dir",
            str(out_dir),
            "--strict",
        ],
    )

    assert result.exit_code == 1


def test_audit_ml_readiness_success(tmp_path: Path):
    run_id = "test-run-ml-success"
    crawl_dir = tmp_path / "crawl_state"
    crawl_dir.mkdir(parents=True)
    db_path = crawl_dir / run_id / "laptops.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    now = datetime.now(UTC)
    product = NormalizedProduct(
        crawl_run_id=run_id,
        scraped_at=now,
        product_name="Asus ROG Strix",
        product_url="https://tokopedia.com/asus-rog",
        canonical_url="https://tokopedia.com/asus-rog",
        listing_key="key-rog-1",
        price=25000000,
        rating=4.8,
        review_count=15,
    )
    store.save(product)

    run_raw_dir = crawl_dir / run_id
    (run_raw_dir / "products.jsonl").write_text(
        json.dumps({
            "listing_key": "key-rog-1",
            "product": {
                "listing_key": "key-rog-1",
                "name": "Asus ROG Strix",
                "price": 25000000,
                "rating": 4.8,
                "review_count": 15,
            }
        }) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "reports_ml"

    result = runner.invoke(
        app,
        [
            "audit-ml-readiness",
            "--run-id",
            run_id,
            "--crawl-dir",
            str(crawl_dir),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert "ML Dataset Readiness Audit Completed" in result.stdout
    assert f"Run: {run_id}" in result.stdout
    assert "Rows: 1" in result.stdout
    assert "Candidate representations:" in result.stdout
    assert "R1 price + rating:" in result.stdout
    assert "R2 price + rating + review_count:" in result.stdout
    assert "Extreme price observations:" in result.stdout
    assert "Missingness review cases:" in result.stdout
    assert "Report:" in result.stdout

    assert (out_dir / "ml_readiness.json").is_file()
    assert (out_dir / "ml_readiness_report.md").is_file()
    assert (out_dir / "extreme_price_review.csv").is_file()
    assert (out_dir / "missingness_cases.csv").is_file()


def test_audit_ml_readiness_sample_extremes_override(tmp_path: Path):
    run_id = "test-run-ml-sample"
    crawl_dir = tmp_path / "crawl_state"
    crawl_dir.mkdir(parents=True)
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    now = datetime.now(UTC)
    product = NormalizedProduct(
        crawl_run_id=run_id,
        scraped_at=now,
        product_name="Lenovo ThinkPad",
        product_url="https://tokopedia.com/thinkpad",
        canonical_url="https://tokopedia.com/thinkpad",
        listing_key="key-thinkpad-1",
        price=18000000,
        rating=4.9,
        review_count=42,
    )
    store.save(product)

    run_raw_dir = crawl_dir / run_id
    run_raw_dir.mkdir(parents=True, exist_ok=True)
    (run_raw_dir / "products.jsonl").write_text(
        json.dumps({
            "listing_key": "key-thinkpad-1",
            "product": {
                "listing_key": "key-thinkpad-1",
                "name": "Lenovo ThinkPad",
                "price": 18000000,
            }
        }) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "reports_sample"

    result = runner.invoke(
        app,
        [
            "audit-ml-readiness",
            "--run-id",
            run_id,
            "--crawl-dir",
            str(crawl_dir),
            "--output-dir",
            str(out_dir),
            "--sample-extremes",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "ml_readiness_report.md").is_file()
