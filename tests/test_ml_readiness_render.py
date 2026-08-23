import csv
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
    write_ml_readiness_artifacts,
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
def sample_report(tmp_path: Path) -> MLReadinessReport:
    db_path = tmp_path / "test.db"
    store = SQLiteStore(db_path)
    run_id = "run_20260823_120000"

    products = [
        NormalizedProduct(
            crawl_run_id=run_id,
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
            crawl_run_id=run_id,
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
            review_count=None,
            talk_count=5,
            rating=None,
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
        NormalizedProduct(
            crawl_run_id=run_id,
            scraped_at="2026-08-23T12:00:00Z",
            product_name="Ultra Expensive Laptop",
            product_url="https://tokopedia.com/shop/ultra-expensive",
            canonical_url="https://tokopedia.com/shop/ultra-expensive",
            product_id="999999",
            listing_key="999999",
            price=990000000.0,
            original_price=990000000.0,
            discount_percent=0.0,
            sold_count=0,
            view_count=100,
            review_count=0,
            talk_count=0,
            rating=0.0,
            brand="Custom",
            category="Laptop",
            subcategory="Workstation",
            shop_name="Extreme Store",
            shop_location="Jakarta Selatan",
            official_store=False,
            source_type="search",
            source_query="laptop gaming",
            source_url="https://tokopedia.com/search?q=laptop+gaming",
            source_page=1,
        ),
    ]

    for prod in products:
        store.save(prod)

    config = create_sample_config()

    report = run_ml_readiness_audit(
        run_id=run_id,
        store=store,
        config=config,
        git_commit="377d590",
        acquisition_tag="dataset-acquisition-v1.0",
        search_contract_sha256="a" * 64,
        feature_audit_sha256="b" * 64,
        readiness_config_sha256="c" * 64,
    )
    store.close()
    return report


def test_renderer_writes_all_required_artifacts(tmp_path: Path, sample_report: MLReadinessReport):
    out_dir = tmp_path / "artifacts"
    paths = write_ml_readiness_artifacts(
        sample_report,
        output_dir=out_dir,
        maximum_extreme_cases=20,
        maximum_missingness_cases=30,
    )

    assert len(paths) == 4
    json_p, md_p, extreme_csv_p, missing_csv_p = paths

    assert json_p.name == "ml_readiness.json"
    assert md_p.name == "ml_readiness_report.md"
    assert extreme_csv_p.name == "extreme_price_review.csv"
    assert missing_csv_p.name == "missingness_cases.csv"

    assert json_p.is_file()
    assert md_p.is_file()
    assert extreme_csv_p.is_file()
    assert missing_csv_p.is_file()


def test_report_does_not_claim_automatic_imputation(tmp_path: Path, sample_report: MLReadinessReport):
    out_dir = tmp_path / "artifacts"
    _, md_p, _, _ = write_ml_readiness_artifacts(
        sample_report,
        output_dir=out_dir,
    )

    text = md_p.read_text(encoding="utf-8").lower()

    assert "imputed to zero" not in text
    assert "automatically removed" not in text
    assert "causes" not in text


def test_markdown_heading_structure(tmp_path: Path, sample_report: MLReadinessReport):
    out_dir = tmp_path / "artifacts"
    _, md_p, _, _ = write_ml_readiness_artifacts(
        sample_report,
        output_dir=out_dir,
    )

    text = md_p.read_text(encoding="utf-8")

    expected_headings = [
        "# ML Dataset Readiness Audit",
        "## 1. Dataset Identity",
        "## 2. Integrity Check",
        "## 3. Candidate Features",
        "## 4. Missingness Analysis",
        "### 4.1 Rating",
        "### 4.2 Review Count",
        "### 4.3 Joint Missingness Patterns",
        "## 5. Complete-Case Analysis",
        "## 6. Distribution Analysis",
        "### 6.1 Price",
        "### 6.2 Rating",
        "### 6.3 Review Count",
        "## 7. Extreme Price Analysis",
        "## 8. Skewness and Transformation Diagnostics",
        "## 9. Variance Analysis",
        "## 10. Correlation and Redundancy",
        "## 11. Candidate Representation Readiness",
        "### R1 — Price + Rating",
        "### R2 — Price + Rating + Review Count",
        "## 12. Unresolved Issues",
        "## 13. ML Dataset Freeze Recommendation",
    ]

    for heading in expected_headings:
        assert heading in text, f"Missing heading: {heading}"

    # Verify freeze recommendation is valid
    valid_recs = ["READY_FOR_HUMAN_FREEZE_REVIEW", "REVIEW_REQUIRED", "NOT_READY"]
    found_rec = False
    for rec in valid_recs:
        if rec in text:
            found_rec = True
            break
    assert found_rec, "Freeze recommendation must be one of READY_FOR_HUMAN_FREEZE_REVIEW, REVIEW_REQUIRED, or NOT_READY"


def test_csv_files_header_and_limit(tmp_path: Path, sample_report: MLReadinessReport):
    out_dir = tmp_path / "artifacts"
    _, _, extreme_csv_p, missing_csv_p = write_ml_readiness_artifacts(
        sample_report,
        output_dir=out_dir,
        maximum_extreme_cases=1,
        maximum_missingness_cases=1,
    )

    # Check extreme CSV headers and limit
    with open(extreme_csv_p, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        expected_extreme_headers = [
            "listing_key",
            "product_name",
            "product_url",
            "price",
            "breadcrumb",
            "shop_name",
            "trigger_names",
            "robust_z_score",
            "raw_price_value",
            "price_source",
            "review_status",
            "review_note",
        ]
        assert headers == expected_extreme_headers
        extreme_rows = list(reader)
        assert len(extreme_rows) <= 1

    # Check missingness CSV headers and limit
    with open(missing_csv_p, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        expected_missing_headers = [
            "listing_key",
            "product_name",
            "product_url",
            "rating",
            "review_count",
            "rating_missing",
            "review_count_missing",
            "semantic_status",
            "evidence",
            "review_note",
        ]
        assert headers == expected_missing_headers
        missing_rows = list(reader)
        assert len(missing_rows) <= 1
