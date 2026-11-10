"""ML Dataset Freeze subsystem.

Reconciles eligibility leakage, resolves review_count semantics,
materializes R1/R2 frozen datasets, and generates cryptographic manifests.
"""

from tokped_market_scrapper.ml_freeze.config import (
    MLFreezeConfig,
    load_ml_freeze_config,
)
from tokped_market_scrapper.ml_freeze.decisions import build_cleaning_decision
from tokped_market_scrapper.ml_freeze.eligibility import (
    EligibilityAssessment,
    assess_ml_eligibility,
)
from tokped_market_scrapper.ml_freeze.freeze import FreezeResult, freeze_ml_dataset
from tokped_market_scrapper.ml_freeze.loader import MLFreezeInput, load_ml_freeze_input
from tokped_market_scrapper.ml_freeze.manifest import build_ml_dataset_manifest
from tokped_market_scrapper.ml_freeze.matrices import FrozenMatrices, build_ml_matrices
from tokped_market_scrapper.ml_freeze.models import (
    CleaningDecision,
    EligibilityDecision,
    EligibilityReason,
    ReviewCountSemanticStatus,
)
from tokped_market_scrapper.ml_freeze.render import write_cleaning_artifacts
from tokped_market_scrapper.ml_freeze.review_semantics import (
    ReviewCountResolution,
    resolve_review_count,
)
from tokped_market_scrapper.ml_freeze.validate import (
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
