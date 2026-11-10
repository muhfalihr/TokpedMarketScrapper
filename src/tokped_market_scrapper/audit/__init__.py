"""Audit module for scientific feature reliability and provenance tracking."""

from laptop_market_scraper.audit.engine import audit_features, classify_suitability
from laptop_market_scraper.audit.models import (
    DatasetIntegrityReport,
    FeatureAuditReport,
    FeatureAuditResult,
    FeatureSuitability,
    ReliabilityStatus,
)
from laptop_market_scraper.audit.render import (
    export_feature_audit,
    render_feature_audit_json,
    render_feature_audit_markdown,
)
from laptop_market_scraper.audit.statistics import (
    NumericFeatureStats,
    calculate_numeric_stats,
)

__all__ = [
    "DatasetIntegrityReport",
    "FeatureAuditReport",
    "FeatureAuditResult",
    "FeatureSuitability",
    "NumericFeatureStats",
    "ReliabilityStatus",
    "audit_features",
    "calculate_numeric_stats",
    "classify_suitability",
    "export_feature_audit",
    "render_feature_audit_json",
    "render_feature_audit_markdown",
]
