"""ML Dataset Freeze subsystem.

Reconciles eligibility leakage, resolves review_count semantics,
materializes R1/R2 frozen datasets, and generates cryptographic manifests.
"""

from laptop_market_scraper.ml_freeze.config import (
    MLFreezeConfig,
    load_ml_freeze_config,
)
from laptop_market_scraper.ml_freeze.decisions import build_cleaning_decision
from laptop_market_scraper.ml_freeze.eligibility import (
    EligibilityAssessment,
    assess_ml_eligibility,
)
from laptop_market_scraper.ml_freeze.freeze import FreezeResult, freeze_ml_dataset
from laptop_market_scraper.ml_freeze.loader import MLFreezeInput, load_ml_freeze_input
from laptop_market_scraper.ml_freeze.manifest import build_ml_dataset_manifest
from laptop_market_scraper.ml_freeze.matrices import FrozenMatrices, build_ml_matrices
from laptop_market_scraper.ml_freeze.models import (
    CleaningDecision,
    EligibilityDecision,
    EligibilityReason,
    ReviewCountSemanticStatus,
)
from laptop_market_scraper.ml_freeze.render import write_cleaning_artifacts
from laptop_market_scraper.ml_freeze.review_semantics import (
    ReviewCountResolution,
    resolve_review_count,
)
from laptop_market_scraper.ml_freeze.validate import (
    FreezeValidationResult,
    validate_frozen_matrices,
)

__all__ = [
    "CleaningDecision",
    "EligibilityAssessment",
    "EligibilityDecision",
    "EligibilityReason",
    "FreezeResult",
    "FreezeValidationResult",
    "FrozenMatrices",
    "MLFreezeConfig",
    "MLFreezeInput",
    "ReviewCountResolution",
    "ReviewCountSemanticStatus",
    "assess_ml_eligibility",
    "build_cleaning_decision",
    "build_ml_dataset_manifest",
    "build_ml_matrices",
    "freeze_ml_dataset",
    "load_ml_freeze_config",
    "load_ml_freeze_input",
    "resolve_review_count",
    "validate_frozen_matrices",
    "write_cleaning_artifacts",
]
