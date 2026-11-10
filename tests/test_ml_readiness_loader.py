from pathlib import Path

import pandas as pd
import pytest

from tokped_market_scrapper.ml_readiness import ReadinessDataset, load_readiness_dataset
from tokped_market_scrapper.models import NormalizedProduct
from tokped_market_scrapper.storage import SQLiteStore


@pytest.fixture
def sample_normalized_product() -> NormalizedProduct:
    return NormalizedProduct(
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
    )


def test_storage_read_methods(tmp_path: Path, sample_normalized_product: NormalizedProduct):
    db_path = tmp_path / "test.db"
    store = SQLiteStore(db_path)

    run_id = sample_normalized_product.crawl_run_id

    # Save data
    store.save(sample_normalized_product)
    store.save_feature_provenance(
        run_id=run_id,
        listing_key=sample_normalized_product.listing_key,
        feature_name="price",
        source_layer="detail",
        source_field="price_raw",
        raw_value="Rp 20.000.000",
        value_kind="numeric",
    )
    store.record_discovery(
        crawl_run_id=run_id,
        listing_key=sample_normalized_product.listing_key,
        source_query="laptop gaming",
        seed_kind="search",
        search_page=1,
        search_start=0,
        search_rows=60,
        search_rank=1,
        category_sc="laptop",
        sort_code="2",
        observed_total_data=100,
        product_name=sample_normalized_product.product_name,
        category_breadcrumb="Computers & Laptops / Laptops",
    )

    # Test read_products_for_run
    products = store.read_products_for_run(run_id)
    assert len(products) == 1
    assert products[0]["listing_key"] == "123456"
    assert products[0]["price"] == 20000000.0

    all_products = store.read_products_for_run(None)
    assert len(all_products) == 1

    # Test read_feature_provenance_for_run
    provenance = store.read_feature_provenance_for_run(run_id)
    assert len(provenance) == 1
    assert provenance[0]["feature_name"] == "price"
    assert provenance[0]["listing_key"] == "123456"

    all_provenance = store.read_feature_provenance_for_run(None)
    assert len(all_provenance) == 1

    # Test read_discoveries_for_run
    discoveries = store.read_discoveries_for_run(run_id)
    assert len(discoveries) == 1
    assert discoveries[0]["source_query"] == "laptop gaming"

    all_discoveries = store.read_discoveries_for_run(None)
    assert len(all_discoveries) == 1

    store.close()


def test_load_readiness_dataset(tmp_path: Path, sample_normalized_product: NormalizedProduct):
    db_path = tmp_path / "test.db"
    raw_jsonl_path = tmp_path / "products.jsonl"
    store = SQLiteStore(db_path)

    run_id = sample_normalized_product.crawl_run_id
    store.save(sample_normalized_product)
    store.save_feature_provenance(
        run_id=run_id,
        listing_key=sample_normalized_product.listing_key,
        feature_name="rating",
        source_layer="detail",
        source_field="rating_raw",
        raw_value="4.8",
    )
    store.record_discovery(
        crawl_run_id=run_id,
        listing_key=sample_normalized_product.listing_key,
        source_query="laptop gaming",
        seed_kind="search",
        search_page=1,
        search_start=0,
        search_rows=60,
        search_rank=1,
        category_sc="laptop",
        sort_code="2",
    )

    # Write raw jsonl mock
    raw_payload = sample_normalized_product.model_dump_json()
    with open(raw_jsonl_path, "w", encoding="utf-8") as f:
        f.write(raw_payload + "\n")

    dataset = load_readiness_dataset(run_id=run_id, store=store, raw_jsonl_path=raw_jsonl_path)

    assert isinstance(dataset, ReadinessDataset)
    assert isinstance(dataset.products, pd.DataFrame)
    assert isinstance(dataset.provenance, pd.DataFrame)
    assert isinstance(dataset.discoveries, pd.DataFrame)

    assert len(dataset.products) == 1
    assert len(dataset.provenance) == 1
    assert len(dataset.discoveries) == 1

    # Verify DataFrames contain expected columns
    expected_cols = {"listing_key", "price", "rating", "review_count", "product_name"}
    assert expected_cols.issubset(set(dataset.products.columns))

    # Verify raw_by_listing_key mapping
    assert "123456" in dataset.raw_by_listing_key
    assert dataset.raw_by_listing_key["123456"]["product_id"] == "123456"

    # Verify frozen dataclass immutability
    with pytest.raises(AttributeError):
        dataset.products = pd.DataFrame()  # type: ignore

    store.close()


def test_load_readiness_dataset_without_raw_jsonl(tmp_path: Path, sample_normalized_product: NormalizedProduct):
    db_path = tmp_path / "test.db"
    store = SQLiteStore(db_path)
    run_id = sample_normalized_product.crawl_run_id
    store.save(sample_normalized_product)

    dataset = load_readiness_dataset(run_id=run_id, store=store)

    assert len(dataset.products) == 1
    assert len(dataset.raw_by_listing_key) == 0

    store.close()
