"""Tests for the audit-features CLI command."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typer.testing import CliRunner

from laptop_market_scraper.cli import app
from laptop_market_scraper.models import NormalizedProduct
from laptop_market_scraper.storage import SQLiteStore

runner = CliRunner()


def test_audit_features_help():
    result = runner.invoke(app, ["audit-features", "--help"])
    assert result.exit_code == 0
    assert "--run-id" in result.stdout
    assert "--crawl-dir" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--strict" in result.stdout


def test_audit_features_success(tmp_path: Path):
    run_id = "test-run-123"
    crawl_dir = tmp_path / "crawl_state"
    crawl_dir.mkdir(parents=True)
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    now = datetime.now(UTC)
    product = NormalizedProduct(
        crawl_run_id=run_id,
        scraped_at=now,
        product_name="Laptop Gaming",
        product_url="https://tokopedia.com/product-1",
        canonical_url="https://tokopedia.com/product-1",
        listing_key="key-1",
        price=15000000,
    )
    store.save(product)

    store.save_feature_provenance(
        run_id=run_id,
        listing_key="key-1",
        feature_name="price",
        source_layer="graphql_search",
        source_field="price",
    )

    # Create raw products.jsonl in crawl_dir / run_id
    run_raw_dir = crawl_dir / run_id
    run_raw_dir.mkdir(parents=True)
    (run_raw_dir / "products.jsonl").write_text(
        json.dumps({"listing_key": "key-1", "title": "Laptop Gaming"}) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "custom_reports"

    result = runner.invoke(
        app,
        [
            "audit-features",
            "--run-id",
            run_id,
            "--crawl-dir",
            str(crawl_dir),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Feature Audit Completed" in result.stdout
    assert f"Run: {run_id}" in result.stdout
    assert "Eligible Products: 1" in result.stdout
    assert "Strong candidates:" in result.stdout
    assert "Conditional:" in result.stdout
    assert "Weak:" in result.stdout
    assert "Unusable:" in result.stdout
    assert "JSON:" in result.stdout
    assert "Markdown:" in result.stdout
    assert (out_dir / "feature_audit.json").is_file()
    assert (out_dir / "feature_audit.md").is_file()


def test_audit_features_default_output_dir(tmp_path: Path):
    run_id = "test-run-456"
    crawl_dir = tmp_path / "crawl_state"
    db_path = crawl_dir / run_id / "laptops.db"
    db_path.parent.mkdir(parents=True)
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    now = datetime.now(UTC)
    product = NormalizedProduct(
        crawl_run_id=run_id,
        scraped_at=now,
        product_name="Laptop Work",
        product_url="https://tokopedia.com/product-2",
        canonical_url="https://tokopedia.com/product-2",
        listing_key="key-2",
        price=8000000,
    )
    store.save(product)

    result = runner.invoke(
        app,
        [
            "audit-features",
            "--run-id",
            run_id,
            "--crawl-dir",
            str(crawl_dir),
        ],
    )

    assert result.exit_code == 0
    expected_out = Path("reports") / run_id
    assert (expected_out / "feature_audit.json").is_file()
    assert (expected_out / "feature_audit.md").is_file()
    if expected_out.exists():
        import shutil

        shutil.rmtree(expected_out)


def test_audit_features_strict_fail(tmp_path: Path):
    run_id = "test-run-strict"
    crawl_dir = tmp_path / "crawl_state"
    crawl_dir.mkdir(parents=True)
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    now = datetime.now(UTC)
    product = NormalizedProduct(
        crawl_run_id=run_id,
        scraped_at=now,
        product_name="Laptop Orphan",
        product_url="https://tokopedia.com/product-orphan",
        canonical_url="https://tokopedia.com/product-orphan",
        listing_key="key-orphan",
        price=10000000,
    )
    store.save(product)

    out_dir = tmp_path / "reports_strict"

    result = runner.invoke(
        app,
        [
            "audit-features",
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
