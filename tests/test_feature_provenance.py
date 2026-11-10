import tempfile
from pathlib import Path

from tokped_market_scrapper.models import FeatureProvenance
from tokped_market_scrapper.storage import SQLiteStore


def test_feature_provenance_model():
    prov = FeatureProvenance(
        crawl_run_id="run_123",
        listing_key="key_abc",
        feature_name="price",
        source_layer="graphql_search",
        source_field="price_int",
        value_kind="numeric",
        raw_value_json="15000000",
        observed_at="2026-08-23T10:00:00Z",
    )
    assert prov.crawl_run_id == "run_123"
    assert prov.listing_key == "key_abc"
    assert prov.feature_name == "price"
    assert prov.source_layer == "graphql_search"
    assert prov.source_field == "price_int"
    assert prov.value_kind == "numeric"
    assert prov.raw_value_json == "15000000"
    assert prov.observed_at == "2026-08-23T10:00:00Z"


def test_save_and_get_feature_provenance():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStore(db_path)

        store.save_feature_provenance(
            run_id="run_1",
            listing_key="item_1",
            feature_name="price",
            source_layer="graphql_search",
            source_field="price_raw",
            raw_value=12000000,
            value_kind="numeric",
        )

        res = store.get_feature_provenance("run_1", "item_1", "price")
        assert res is not None
        assert res.crawl_run_id == "run_1"
        assert res.listing_key == "item_1"
        assert res.feature_name == "price"
        assert res.source_layer == "graphql_search"
        assert res.source_field == "price_raw"
        assert res.value_kind == "numeric"
        assert res.raw_value_json == "12000000"
        assert res.observed_at is not None

        # Test non-existent record
        assert store.get_feature_provenance("run_1", "item_1", "non_existent") is None

        store.close()


def test_feature_provenance_replace():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStore(db_path)

        store.save_feature_provenance(
            run_id="run_1",
            listing_key="item_1",
            feature_name="price",
            source_layer="graphql_search",
            source_field="price_raw",
            raw_value=100,
        )

        store.save_feature_provenance(
            run_id="run_1",
            listing_key="item_1",
            feature_name="price",
            source_layer="product_detail_html",
            source_field="price_detail",
            raw_value=200,
        )

        res = store.get_feature_provenance("run_1", "item_1", "price")
        assert res is not None
        assert res.source_layer == "product_detail_html"
        assert res.source_field == "price_detail"
        assert res.raw_value_json == "200"

        store.close()


def test_get_all_feature_provenance():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStore(db_path)

        store.save_feature_provenance("run_1", "item_1", "price", "graphql_search", "price_field", 100)
        store.save_feature_provenance("run_1", "item_1", "rating", "derived", "rating_field", 4.5)
        store.save_feature_provenance("run_2", "item_2", "price", "graphql_search", "price_field", 300)

        run1_records = store.get_all_feature_provenance("run_1")
        assert len(run1_records) == 2
        feature_names = {r.feature_name for r in run1_records}
        assert feature_names == {"price", "rating"}

        run2_records = store.get_all_feature_provenance("run_2")
        assert len(run2_records) == 1
        assert run2_records[0].listing_key == "item_2"

        store.close()
