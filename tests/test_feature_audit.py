import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from laptop_market_scraper.audit.engine import audit_features, classify_suitability
from laptop_market_scraper.audit.models import (
    FeatureAuditReport,
    FeatureSuitability,
    ReliabilityStatus,
)
from laptop_market_scraper.models import NormalizedProduct
from laptop_market_scraper.storage import SQLiteStore


def test_classify_suitability_unusable():
    # Zero coverage
    assert (
        classify_suitability(
            coverage_percent=0.0,
            reliability=ReliabilityStatus.VERIFIED_EXACT,
            unique_count=5,
            row_count=10,
        )
        == FeatureSuitability.UNUSABLE
    )

    # Unavailable reliability
    assert (
        classify_suitability(
            coverage_percent=100.0,
            reliability=ReliabilityStatus.UNAVAILABLE,
            unique_count=5,
            row_count=10,
        )
        == FeatureSuitability.UNUSABLE
    )

    # Constant value across multiple rows
    assert (
        classify_suitability(
            coverage_percent=100.0,
            reliability=ReliabilityStatus.VERIFIED_EXACT,
            unique_count=1,
            row_count=10,
        )
        == FeatureSuitability.UNUSABLE
    )


def test_classify_suitability_strong_candidate():
    assert (
        classify_suitability(
            coverage_percent=85.0,
            reliability=ReliabilityStatus.VERIFIED_EXACT,
            unique_count=10,
            row_count=20,
        )
        == FeatureSuitability.STRONG_CANDIDATE
    )

    assert (
        classify_suitability(
            coverage_percent=80.0,
            reliability=ReliabilityStatus.VERIFIED_APPROXIMATE,
            unique_count=5,
            row_count=10,
        )
        == FeatureSuitability.STRONG_CANDIDATE
    )


def test_classify_suitability_conditional():
    # High coverage but context dependent reliability
    assert (
        classify_suitability(
            coverage_percent=85.0,
            reliability=ReliabilityStatus.CONTEXT_DEPENDENT,
            unique_count=5,
            row_count=10,
        )
        == FeatureSuitability.CONDITIONAL
    )

    # Moderate coverage (>= 50%)
    assert (
        classify_suitability(
            coverage_percent=55.0,
            reliability=ReliabilityStatus.SEMANTICS_UNVERIFIED,
            unique_count=5,
            row_count=10,
        )
        == FeatureSuitability.CONDITIONAL
    )

    # Low coverage but context dependent
    assert (
        classify_suitability(
            coverage_percent=30.0,
            reliability=ReliabilityStatus.CONTEXT_DEPENDENT,
            unique_count=5,
            row_count=10,
        )
        == FeatureSuitability.CONDITIONAL
    )


def test_classify_suitability_weak_candidate():
    assert (
        classify_suitability(
            coverage_percent=40.0,
            reliability=ReliabilityStatus.SEMANTICS_UNVERIFIED,
            unique_count=5,
            row_count=10,
        )
        == FeatureSuitability.WEAK_CANDIDATE
    )


def test_audit_features_populated_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStore(db_path)
        run_id = "run_audit_101"

        # Save normalized products
        p1 = NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at=datetime.now(UTC),
            product_name="Laptop A",
            product_url="https://tokopedia.com/a",
            canonical_url="https://tokopedia.com/a",
            listing_key="key_a",
            price=15000000,
            original_price=18000000,
            discount_percent=16.67,
            sold_count=50,
            rating=4.8,
            review_count=10,
        )
        p2 = NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at=datetime.now(UTC),
            product_name="Laptop B",
            product_url="https://tokopedia.com/b",
            canonical_url="https://tokopedia.com/b",
            listing_key="key_b",
            price=20000000,
            rating=4.5,
            review_count=5,
        )
        store.save(p1)
        store.save(p2)

        # Save discovery
        store.record_discovery(
            crawl_run_id=run_id,
            listing_key="key_a",
            source_query="laptop",
            seed_kind="generic",
            search_page=1,
            search_start=0,
            search_rows=60,
            search_rank=1,
            category_sc="laptop",
            sort_code="23",
        )

        # Save provenance
        store.save_feature_provenance(
            run_id=run_id,
            listing_key="key_a",
            feature_name="price",
            source_layer="graphql_search",
            source_field="price_int",
            raw_value=15000000,
        )
        store.save_feature_provenance(
            run_id=run_id,
            listing_key="key_b",
            feature_name="price",
            source_layer="graphql_search",
            source_field="price_int",
            raw_value=20000000,
        )

        report = audit_features(run_id=run_id, store=store)

        assert isinstance(report, FeatureAuditReport)
        assert report.run_id == run_id
        assert report.total_eligible_listings == 2
        assert report.integrity.sqlite_product_count == 2
        assert report.integrity.sqlite_discovery_count == 1
        assert report.integrity.provenance_record_count == 2

        # Check candidate feature results
        assert len(report.results) == 10
        res_dict = {res.feature_name: res for res in report.results}

        # Price check (100% coverage, 2 unique values)
        price_res = res_dict["price"]
        assert price_res.coverage_percent == 100.0
        assert price_res.missingness_percent == 0.0
        assert price_res.source_layers == {"graphql_search": 2}
        assert price_res.source_fields == {"price_int": 2}
        assert price_res.minimum == 15000000.0
        assert price_res.maximum == 20000000.0
        assert price_res.suitability == FeatureSuitability.STRONG_CANDIDATE

        # Discount percent check (50% coverage)
        disc_res = res_dict["discount_percent"]
        assert disc_res.coverage_percent == 50.0
        assert disc_res.missingness_percent == 50.0

        store.close()


def test_audit_features_integrity_raw_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test.db"
        store = SQLiteStore(db_path)
        run_id = "run_audit_raw"

        # SQLite products
        p1 = NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at=datetime.now(UTC),
            product_name="Laptop X",
            product_url="https://tokopedia.com/x",
            canonical_url="https://tokopedia.com/x",
            listing_key="key_x",
            price=10000000,
        )
        p2 = NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at=datetime.now(UTC),
            product_name="Laptop Y",
            product_url="https://tokopedia.com/y",
            canonical_url="https://tokopedia.com/y",
            listing_key="key_y",
            price=12000000,
        )
        store.save(p1)
        store.save(p2)

        # Save provenance for key_x only
        store.save_feature_provenance(
            run_id=run_id,
            listing_key="key_x",
            feature_name="price",
            source_layer="graphql_search",
            source_field="price_int",
        )

        # Raw JSONL directory
        raw_dir = tmp_path / "raw_data"
        raw_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = raw_dir / "products.jsonl"

        # jsonl contains key_x and key_z (key_z is orphan raw, key_y is missing raw counterpart)
        with open(jsonl_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"listing_key": "key_x", "product_name": "Laptop X"}) + "\n")
            f.write(json.dumps({"listing_key": "key_z", "product_name": "Laptop Z"}) + "\n")

        report = audit_features(run_id=run_id, store=store, raw_dir=raw_dir)

        assert report.integrity.sqlite_product_count == 2
        assert report.integrity.raw_jsonl_count == 2
        assert report.integrity.missing_raw_counterparts == 1  # key_y is in SQLite but not raw
        assert report.integrity.orphan_raw_records == 1  # key_z is in raw but not SQLite
        assert report.integrity.orphan_normalized_records == 1  # key_y has no provenance

        store.close()
