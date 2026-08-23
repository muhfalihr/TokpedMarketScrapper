from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

REQUIRED_FEATURES: tuple[str, ...] = ("price", "rating", "review_count")


class RepresentationConfig(BaseModel):
    id: str
    description: str
    features: list[str]


class ExtremesConfig(BaseModel):
    price_lower_quantile: float = Field(..., gt=0.0, lt=1.0)
    price_upper_quantile: float = Field(..., gt=0.0, lt=1.0)
    iqr_multiplier: float = Field(..., gt=0.0)
    robust_z_threshold: float = Field(..., gt=0.0)
    sample_limit: int = Field(default=20, gt=0)

    @model_validator(mode="after")
    def validate_quantile_range(self) -> Self:
        if self.price_lower_quantile >= self.price_upper_quantile:
            raise ValueError(
                f"price_lower_quantile ({self.price_lower_quantile}) must be strictly less than "
                f"price_upper_quantile ({self.price_upper_quantile})"
            )
        return self


class AssociationConfig(BaseModel):
    spearman_redundancy_threshold: float = Field(..., ge=0.0, le=1.0)


class MLReadinessConfig(BaseModel):
    features: list[str]
    representations: dict[str, RepresentationConfig]
    extremes: ExtremesConfig
    association: AssociationConfig

    @field_validator("features")
    @classmethod
    def validate_required_features(cls, features: list[str]) -> list[str]:
        missing = set(REQUIRED_FEATURES) - set(features)
        if missing:
            raise ValueError(f"features missing required entries: {sorted(missing)}")
        return features


def load_ml_readiness_config(path: Path | str = "config/ml_readiness.yaml") -> MLReadinessConfig:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return MLReadinessConfig.model_validate(data)


class IntegrityResult(BaseModel):
    normalized_rows: int
    raw_rows: int
    unique_normalized_keys: int
    unique_raw_keys: int
    duplicate_normalized_keys: tuple[str, ...]
    orphan_normalized_records: int
    orphan_raw_records: int
    missing_required_columns: tuple[str, ...]
    invalid_price_keys: tuple[str, ...]
    invalid_rating_keys: tuple[str, ...]
    invalid_review_count_keys: tuple[str, ...]
    passed: bool


from enum import Enum


class MissingSemanticStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    LIKELY = "LIKELY"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class MissingnessCase(BaseModel):
    listing_key: str
    product_name: str | None = None
    product_url: str | None = None
    rating: float | None = None
    review_count: float | None = None
    rating_missing: bool
    review_count_missing: bool
    semantic_status: MissingSemanticStatus
    evidence: tuple[str, ...]


class MissingnessResult(BaseModel):
    total_rows: int
    complete_rating_and_reviews: int
    missing_rating_only: int
    missing_reviews_only: int
    missing_both: int
    rating_missing_percent: float
    review_missing_percent: float
    median_price_when_review_present: float | None = None
    median_price_when_review_missing: float | None = None
    cases: tuple[MissingnessCase, ...]


class CompleteCaseResult(BaseModel):
    representation_id: str
    required_features: tuple[str, ...]
    total_rows: int
    complete_rows: int
    dropped_rows: int
    retention_percent: float
    dropped_percent: float
    complete_listing_keys: tuple[str, ...]


class TransformationSignal(str, Enum):
    LOG1P_RECOMMENDED = "LOG1P_RECOMMENDED"
    LOG1P_OPTIONAL = "LOG1P_OPTIONAL"
    RAW_PRESERVED = "RAW_PRESERVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DistributionResult(BaseModel):
    feature_name: str
    non_null_count: int
    missing_count: int
    coverage_percent: float
    min_value: float | None = None
    q01: float | None = None
    q25: float | None = None
    median: float | None = None
    q75: float | None = None
    q99: float | None = None
    max_value: float | None = None
    iqr: float | None = None
    raw_skewness: float | None = None
    log1p_skewness: float | None = None
    absolute_skew_reduction: float | None = None
    variance: float | None = None
    std_dev: float | None = None
    zero_count: int
    zero_rate: float
    unique_value_count: int
    dominant_value_count: int
    dominant_value_rate: float
    zero_variance_flag: bool
    near_zero_variance_flag: bool
    transformation_signal: TransformationSignal


class ExtremePriceObservation(BaseModel):
    listing_key: str
    product_name: str | None = None
    product_url: str | None = None
    price: float
    breadcrumb: str | None = None
    shop_name: str | None = None
    lower_quantile_flag: bool
    upper_quantile_flag: bool
    iqr_flag: bool
    robust_z_flag: bool
    robust_z_score: float | None = None
    trigger_names: tuple[str, ...]
    raw_price_value: str | int | float | None = None
    price_source: str | None = None
    review_status: str = "UNREVIEWED"
    review_note: str = ""


class AssociationResult(BaseModel):
    feature_a: str
    feature_b: str
    pairwise_n: int
    spearman_rho: float | None = None
    pearson_r: float | None = None
    strength: str | None = None
    redundancy_review: bool


class RepresentationStatus(str, Enum):
    READY = "READY"
    READY_WITH_CAVEATS = "READY_WITH_CAVEATS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_READY = "NOT_READY"


class RepresentationReadiness(BaseModel):
    representation_id: str
    required_features: tuple[str, ...]
    status: RepresentationStatus
    caveats: tuple[str, ...] = ()
    complete_rows: int
    retention_percent: float


