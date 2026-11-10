from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ReliabilityStatus(str, Enum):
    VERIFIED_EXACT = "VERIFIED_EXACT"
    VERIFIED_APPROXIMATE = "VERIFIED_APPROXIMATE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    SEMANTICS_UNVERIFIED = "SEMANTICS_UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"


class FeatureSuitability(str, Enum):
    STRONG_CANDIDATE = "STRONG_CANDIDATE"
    CONDITIONAL = "CONDITIONAL"
    WEAK_CANDIDATE = "WEAK_CANDIDATE"
    UNUSABLE = "UNUSABLE"


class FeatureRegistryEntry(BaseModel):
    feature_name: str
    research_dimension: Literal["Pricing", "Demand", "Engagement", "Perception"]
    expected_dtype: str
    nullable: bool
    semantic_description: str
    known_semantic_limitations: str
    default_reliability: ReliabilityStatus


class FeatureAuditResult(BaseModel):
    feature_name: str
    research_dimension: str
    coverage_percent: float
    missingness_percent: float
    observed_dtype: str
    source_layers: dict[str, int] = Field(default_factory=dict)
    source_fields: dict[str, int] = Field(default_factory=dict)
    minimum: float | None = None
    q1: float | None = None
    median: float | None = None
    q3: float | None = None
    maximum: float | None = None
    skewness: float | None = None
    reliability: ReliabilityStatus
    semantic_note: str
    suitability: FeatureSuitability


class DatasetIntegrityReport(BaseModel):
    sqlite_product_count: int
    sqlite_discovery_count: int
    provenance_record_count: int
    raw_jsonl_count: int
    missing_raw_counterparts: int
    orphan_raw_records: int
    orphan_normalized_records: int


class FeatureAuditReport(BaseModel):
    run_id: str
    generated_at: str
    total_eligible_listings: int
    integrity: DatasetIntegrityReport
    results: list[FeatureAuditResult] = Field(default_factory=list)
