import json
import tempfile
from pathlib import Path

import pytest
from laptop_market_scraper.audit import (
    DatasetIntegrityReport,
    FeatureAuditReport,
    FeatureAuditResult,
    FeatureSuitability,
    ReliabilityStatus,
    export_feature_audit,
    render_feature_audit_json,
    render_feature_audit_markdown,
)


@pytest.fixture
def sample_audit_report() -> FeatureAuditReport:
    integrity = DatasetIntegrityReport(
        sqlite_product_count=100,
        sqlite_discovery_count=120,
        provenance_record_count=200,
        raw_jsonl_count=100,
        missing_raw_counterparts=0,
        orphan_raw_records=0,
        orphan_normalized_records=0,
    )
    results = [
        FeatureAuditResult(
            feature_name="price",
            research_dimension="Pricing",
            coverage_percent=100.0,
            missingness_percent=0.0,
            observed_dtype="float64",
            source_layers={"graphql_search": 100},
            source_fields={"price_int": 100},
            minimum=5000000.0,
            q1=10000000.0,
            median=15000000.0,
            q3=20000000.0,
            maximum=45000000.0,
            skewness=1.25,
            reliability=ReliabilityStatus.VERIFIED_EXACT,
            semantic_note="Verified exact price from listing",
            suitability=FeatureSuitability.STRONG_CANDIDATE,
        ),
        FeatureAuditResult(
            feature_name="discount_percent",
            research_dimension="Pricing",
            coverage_percent=45.0,
            missingness_percent=55.0,
            observed_dtype="float64",
            source_layers={"graphql_search": 45},
            source_fields={"discount": 45},
            minimum=5.0,
            q1=10.0,
            median=15.0,
            q3=25.0,
            maximum=50.0,
            skewness=0.5,
            reliability=ReliabilityStatus.CONTEXT_DEPENDENT,
            semantic_note="Only available when listing has active discount",
            suitability=FeatureSuitability.CONDITIONAL,
        ),
        FeatureAuditResult(
            feature_name="talk_count",
            research_dimension="Engagement",
            coverage_percent=20.0,
            missingness_percent=80.0,
            observed_dtype="float64",
            source_layers={"pdp_detail": 20},
            source_fields={"talk_count": 20},
            minimum=0.0,
            q1=1.0,
            median=2.0,
            q3=5.0,
            maximum=20.0,
            skewness=2.1,
            reliability=ReliabilityStatus.SEMANTICS_UNVERIFIED,
            semantic_note="Sparse field from product detail page",
            suitability=FeatureSuitability.WEAK_CANDIDATE,
        ),
        FeatureAuditResult(
            feature_name="transaction_reject",
            research_dimension="Engagement",
            coverage_percent=0.0,
            missingness_percent=100.0,
            observed_dtype="float64",
            source_layers={},
            source_fields={},
            minimum=None,
            q1=None,
            median=None,
            q3=None,
            maximum=None,
            skewness=None,
            reliability=ReliabilityStatus.UNAVAILABLE,
            semantic_note="Field deprecated or not exposed by API",
            suitability=FeatureSuitability.UNUSABLE,
        ),
    ]
    return FeatureAuditReport(
        run_id="run_test_render_001",
        generated_at="2026-08-23T11:00:00+00:00",
        total_eligible_listings=100,
        integrity=integrity,
        results=results,
    )


def test_render_feature_audit_json(sample_audit_report: FeatureAuditReport):
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "sub" / "feature_audit.json"
        res_path = render_feature_audit_json(sample_audit_report, output_path)

        assert res_path == output_path
        assert output_path.is_file()

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["run_id"] == "run_test_render_001"
        assert data["total_eligible_listings"] == 100
        assert len(data["results"]) == 4
        assert data["integrity"]["sqlite_product_count"] == 100


def test_render_feature_audit_markdown(sample_audit_report: FeatureAuditReport):
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "feature_audit.md"
        res_path = render_feature_audit_markdown(sample_audit_report, output_path)

        assert res_path == output_path
        assert output_path.is_file()

        text = output_path.read_text(encoding="utf-8")

        # Required main header and metadata
        assert "# Feature Availability Audit" in text
        assert "- **Run ID**: `run_test_render_001`" in text
        assert "- **Generated At**: `2026-08-23T11:00:00+00:00`" in text
        assert "- **Total Eligible Listings**: `100`" in text

        # Primary Summary Table header
        assert "## Primary Summary Table" in text
        expected_headers = [
            "Feature",
            "Dimension",
            "Coverage",
            "Missing",
            "Type",
            "Main Source",
            "Median",
            "Min–Max",
            "Reliability",
            "Suitability",
        ]
        for header in expected_headers:
            assert header in text

        # Table rows content
        assert "price" in text
        assert "Pricing" in text
        assert "100.0%" in text
        assert "VERIFIED_EXACT" in text
        assert "STRONG_CANDIDATE" in text

        # Required Research Recommendation Summary section
        assert "## Research Recommendation Summary" in text
        assert "- **Strong Candidates**: price" in text
        assert "- **Conditional Candidates**: discount_percent" in text
        assert "- **Weak Candidates**: talk_count" in text
        assert "- **Unusable Features**: transaction_reject" in text


def test_export_feature_audit(sample_audit_report: FeatureAuditReport):
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "output_reports"
        json_path, md_path = export_feature_audit(sample_audit_report, out_dir)

        assert json_path.is_file()
        assert md_path.is_file()
        assert json_path.name == "feature_audit.json"
        assert md_path.name == "feature_audit.md"
        assert json_path.parent == out_dir
        assert md_path.parent == out_dir
