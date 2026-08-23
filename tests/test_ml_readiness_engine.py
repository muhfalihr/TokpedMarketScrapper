import json
from pathlib import Path

import pytest

from laptop_market_scraper.ml_readiness import (
    AssociationConfig,
    AuditProvenance,
    ExtremesConfig,
    MLReadinessConfig,
    MLReadinessReport,
    RepresentationConfig,
    run_ml_readiness_audit,
)
from laptop_market_scraper.models import NormalizedProduct
from laptop_market_scraper.storage import SQLiteStore


def create_sample_config() -> MLReadinessConfig:
    return MLReadinessConfig(
        features=["price", "rating", "review_count"],
        representations={
            "R1": RepresentationConfig(
                id="R1",
                description="Core price, rating, review_count features",
                features=["price", "rating", "review_count"],
            ),
            "R2": RepresentationConfig(
                id="R2",
                description="Price and review_count features",
                features=["price", "review_count"],
            ),
        },
        extremes=ExtremesConfig(
            price_lower_quantile=0.01,
            price_upper_quantile=0.99,
            iqr_multiplier=1.5,
            robust_z_threshold=3.5,
            sample_limit=20,
        ),
        association=AssociationConfig(
            spearman_redundancy_threshold=0.85,
        ),
    )


@pytest.fixture
def sample_products() -> list[NormalizedProduct]:
    return [
        NormalizedProduct(
            crawl_run_id="run_20260823_120000",
            scraped_at="2026-08-23T12:00:00Z",
            product_name="Asus ROG Zephyrus G14",
            product_url="https://tokopedia.com/shop/asus-rog-g14",
            canonical_url="https://tokopedia.com/shop/asus-rog-g14",
            product_id="123456",
            listing_key="123456",
            price=20000000.0,
            original_price=22000000.0,
            discount_percent=9.0,
            sold_count=15,
            view_count=500,
            review_count=10,
            talk_count=2,
            rating=4.8,
            brand="Asus",
            category="Laptop",
            subcategory="Gaming",
            shop_name="Official Asus Store",
            shop_location="Jakarta Pusat",
            official_store=True,
            source_type="search",
            source_query="laptop gaming",
            source_url="https://tokopedia.com/search?q=laptop+gaming",
            source_page=1,
        ),
        NormalizedProduct(
            crawl_run_id="run_20260823_120000",
            scraped_at="2026-08-23T12:00:00Z",
            product_name="Lenovo Legion 5 Pro",
            product_url="https://tokopedia.com/shop/lenovo-legion-5",
            canonical_url="https://tokopedia.com/shop/lenovo-legion-5",
            product_id="654321",
            listing_key="654321",
            price=18000000.0,
            original_price=19500000.0,
            discount_percent=7.5,
            sold_count=25,
            view_count=800,
            review_count=20,
            talk_count=5,
            rating=4.9,
            brand="Lenovo",
            category="Laptop",
            subcategory="Gaming",
            shop_name="Lenovo Official Store",
            shop_location="Jakarta Barat",
            official_store=True,
            source_type="search",
            source_query="laptop gaming",
            source_url="https://tokopedia.com/search?q=laptop+gaming",
            source_page=1,
        ),
    ]


def test_engine_generates_r1_and_r2_readiness(tmp_path: Path, sample_products: list[NormalizedProduct]):
    db_path = tmp_path / "test.db"
    raw_jsonl_path = tmp_path / "products.jsonl"
    store = SQLiteStore(db_path)
    run_id = "run_20260823_120000"

    for prod in sample_products:
        store.save(prod)
        store.save_feature_provenance(
            run_id=run_id,
            listing_key=prod.listing_key,
            feature_name="price",
            source_layer="detail",
            source_field="price_raw",
            raw_value=str(prod.price),
        )
        store.record_discovery(
            crawl_run_id=run_id,
            listing_key=prod.listing_key,
            source_query="laptop gaming",
            seed_kind="search",
            search_page=1,
            search_start=0,
            search_rows=60,
            search_rank=1,
            category_sc="laptop",
            sort_code="2",
        )

    # Write raw jsonl
    with open(raw_jsonl_path, "w", encoding="utf-8") as f:
        for prod in sample_products:
            f.write(prod.model_dump_json() + "\n")

    config = create_sample_config()

    report = run_ml_readiness_audit(
        run_id=run_id,
        store=store,
        raw_jsonl_path=raw_jsonl_path,
        config=config,
        git_commit="377d590",
        acquisition_tag="dataset-acquisition-v1.0",
        search_contract_sha256="a" * 64,
        feature_audit_sha256="b" * 64,
        readiness_config_sha256="c" * 64,
    )

    assert isinstance(report, MLReadinessReport)
    assert report.run_id == run_id
    assert report.dataset_rows == 2
    assert report.integrity.passed is True
    assert report.missingness.total_rows == 2

    assert set(report.complete_cases.keys()) == {"R1", "R2"}
    assert set(report.distributions.keys()) == {"price", "rating", "review_count"}
    assert set(report.representations.keys()) == {"R1", "R2"}

    assert isinstance(report.provenance, AuditProvenance)
    assert report.provenance.git_commit == "377d590"
    assert report.provenance.acquisition_tag == "dataset-acquisition-v1.0"
    assert report.provenance.search_contract_sha256 == "a" * 64
    assert report.provenance.feature_audit_sha256 == "b" * 64
    assert report.provenance.readiness_config_sha256 == "c" * 64

    store.close()


def test_engine_default_config_loading(tmp_path: Path, sample_products: list[NormalizedProduct]):
    db_path = tmp_path / "test.db"
    store = SQLiteStore(db_path)
    run_id = "run_20260823_120000"

    for prod in sample_products:
        store.save(prod)

    report = run_ml_readiness_audit(
        run_id=run_id,
        store=store,
    )

    assert isinstance(report, MLReadinessReport)
    assert report.dataset_rows == 2
    assert "price" in report.distributions
    assert report.provenance.git_commit == "unknown"
    assert report.provenance.acquisition_tag == "dataset-acquisition-v1.0"

    store.close()


def test_realistic_readiness_fixture_preserves_all_source_rows(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "ml_readiness" / "expected_cases.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    db_path = tmp_path / "test.db"
    raw_jsonl_path = tmp_path / "products.jsonl"
    store = SQLiteStore(db_path)
    run_id = "run_20260823_130000"

    with open(raw_jsonl_path, "w", encoding="utf-8") as jsonl_file:
        for case in cases:
            listing_key = case["listing_key"]
            price = case["price"]
            rating = case["rating"]
            review_count = case["review_count"]

            prod = NormalizedProduct(
                crawl_run_id=run_id,
                scraped_at="2026-08-23T13:00:00Z",
                product_name=f"Laptop {listing_key}",
                product_url=f"https://tokopedia.com/product/{listing_key}",
                canonical_url=f"https://tokopedia.com/product/{listing_key}",
                product_id=listing_key,
                listing_key=listing_key,
                price=price,
                rating=rating,
                review_count=review_count,
            )
            store.save(prod)
            jsonl_file.write(prod.model_dump_json() + "\n")

    report = run_ml_readiness_audit(
        run_id=run_id,
        store=store,
        raw_jsonl_path=raw_jsonl_path,
    )

    assert report.dataset_rows == 6
    assert report.complete_cases["R1"].complete_rows == 4
    assert report.complete_cases["R2"].complete_rows == 3

    extreme_prices = {obs.price for obs in report.extreme_prices}
    assert 3600.0 in extreme_prices
    assert 189999008.0 in extreme_prices

    store.close()
