import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from laptop_market_scraper.audit.models import (
    DatasetIntegrityReport,
    FeatureAuditReport,
    FeatureAuditResult,
    FeatureSuitability,
    ReliabilityStatus,
)
from laptop_market_scraper.audit.registry import CANDIDATE_FEATURES, FEATURE_REGISTRY
from laptop_market_scraper.audit.statistics import calculate_numeric_stats
from laptop_market_scraper.storage import SQLiteStore


def classify_suitability(
    coverage_percent: float,
    reliability: ReliabilityStatus,
    unique_count: int,
    row_count: int,
) -> FeatureSuitability:
    """Classify feature suitability for ML feature engineering and analysis based on audit metrics."""
    if (
        coverage_percent == 0.0
        or reliability == ReliabilityStatus.UNAVAILABLE
        or (unique_count == 1 and row_count > 1)
    ):
        return FeatureSuitability.UNUSABLE
    elif coverage_percent >= 80.0 and reliability in (
        ReliabilityStatus.VERIFIED_EXACT,
        ReliabilityStatus.VERIFIED_APPROXIMATE,
    ):
        return FeatureSuitability.STRONG_CANDIDATE
    elif coverage_percent >= 50.0 or reliability == ReliabilityStatus.CONTEXT_DEPENDENT:
        return FeatureSuitability.CONDITIONAL
    else:
        return FeatureSuitability.WEAK_CANDIDATE


def audit_features(
    *,
    run_id: str,
    store: SQLiteStore,
    raw_dir: Path | str | None = None,
) -> FeatureAuditReport:
    """Perform a comprehensive feature audit for a given crawl run_id across products and provenance."""
    products = store.get_all_products(run_id=run_id)
    provenance_list = store.get_all_feature_provenance(run_id=run_id)
    discovery_count = store.count_discoveries(crawl_run_id=run_id)

    total_eligible_listings = len(products)
    sqlite_product_count = len(products)
    sqlite_discovery_count = discovery_count
    provenance_record_count = len(provenance_list)

    sqlite_listing_keys = {p.listing_key for p in products}
    prov_listing_keys = {prov.listing_key for prov in provenance_list}
    orphan_normalized_records = len(sqlite_listing_keys - prov_listing_keys)

    raw_jsonl_count = 0
    missing_raw_counterparts = 0
    orphan_raw_records = 0

    if raw_dir is not None:
        base_raw = Path(raw_dir)
        candidates = [
            base_raw / "products.jsonl",
            base_raw / run_id / "products.jsonl",
            base_raw / "raw" / run_id / "products.jsonl",
        ]
        target_file = next((p for p in candidates if p.is_file()), None)

        if target_file is not None:
            raw_records = []
            with open(target_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        try:
                            raw_records.append(json.loads(line_str))
                        except (json.JSONDecodeError, ValueError):
                            pass
            raw_jsonl_count = len(raw_records)
            raw_listing_keys = {
                r.get("listing_key")
                for r in raw_records
                if isinstance(r, dict) and r.get("listing_key")
            }
            missing_raw_counterparts = len(sqlite_listing_keys - raw_listing_keys)
            orphan_raw_records = len(raw_listing_keys - sqlite_listing_keys)

    integrity = DatasetIntegrityReport(
        sqlite_product_count=sqlite_product_count,
        sqlite_discovery_count=sqlite_discovery_count,
        provenance_record_count=provenance_record_count,
        raw_jsonl_count=raw_jsonl_count,
        missing_raw_counterparts=missing_raw_counterparts,
        orphan_raw_records=orphan_raw_records,
        orphan_normalized_records=orphan_normalized_records,
    )

    results: list[FeatureAuditResult] = []

    for feature_name in CANDIDATE_FEATURES:
        entry = FEATURE_REGISTRY[feature_name]
        values = [getattr(p, feature_name, None) for p in products]
        stats = calculate_numeric_stats(values, expected_dtype=entry.expected_dtype)

        feature_provs = [p for p in provenance_list if p.feature_name == feature_name]
        source_layers = dict(Counter(p.source_layer for p in feature_provs))
        source_fields = dict(Counter(p.source_field for p in feature_provs))

        reliability = entry.default_reliability
        for prov in feature_provs:
            if hasattr(prov, "reliability") and prov.reliability:
                reliability = prov.reliability
                break

        suitability = classify_suitability(
            coverage_percent=stats.coverage_percent,
            reliability=reliability,
            unique_count=stats.unique_count,
            row_count=stats.row_count,
        )

        audit_result = FeatureAuditResult(
            feature_name=feature_name,
            research_dimension=entry.research_dimension,
            coverage_percent=stats.coverage_percent,
            missingness_percent=stats.missingness_percent,
            observed_dtype=stats.observed_dtype,
            source_layers=source_layers,
            source_fields=source_fields,
            minimum=stats.minimum,
            q1=stats.q1,
            median=stats.median,
            q3=stats.q3,
            maximum=stats.maximum,
            skewness=stats.skewness,
            reliability=reliability,
            semantic_note=entry.known_semantic_limitations,
            suitability=suitability,
        )
        results.append(audit_result)

    return FeatureAuditReport(
        run_id=run_id,
        generated_at=datetime.now(UTC).isoformat(),
        total_eligible_listings=total_eligible_listings,
        integrity=integrity,
        results=results,
    )
