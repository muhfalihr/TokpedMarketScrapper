from pathlib import Path

import pytest
from pydantic import ValidationError

from laptop_market_scraper.ml_freeze.config import load_ml_freeze_config
from laptop_market_scraper.ml_freeze.models import (
    CleaningDecision,
    EligibilityDecision,
    EligibilityReason,
    FreezeEligibilityConfig,
    FreezeRepresentation,
    FreezeReviewCountConfig,
    MLFreezeConfig,
    ReviewCountSemanticStatus,
)


def test_freeze_config_locks_r1_and_r2():
    config = load_ml_freeze_config(Path("config/ml_freeze.yaml"))

    assert config.artifact_name == "ml-dataset-v1.0"

    assert config.representations["R1"].features == (
        "price",
        "rating",
    )

    assert config.representations["R2"].features == (
        "price",
        "rating",
        "review_count",
    )

    assert config.review_count.allow_semantic_zero_recode is False


def test_load_actual_yaml_config():
    config = load_ml_freeze_config("config/ml_freeze.yaml")
    assert config.version == "1.0"
    assert config.artifact_name == "ml-dataset-v1.0"
    assert "R1" in config.representations
    assert "R2" in config.representations
    assert config.eligibility.allow_ambiguous_in_ml is False
    assert "charger" in config.eligibility.accessory_terms
    assert "lcd" in config.eligibility.component_terms
    assert "dp" in config.eligibility.invalid_price_terms
    assert config.review_count.default_missing_policy == "KEEP_MISSING"
    assert "listing_key" in config.outputs.include_identity_columns


def test_reject_invalid_r1_features():
    with pytest.raises(ValidationError, match="R1"):
        MLFreezeConfig(
            representations={
                "R1": FreezeRepresentation(features=("price",)),
                "R2": FreezeRepresentation(features=("price", "rating", "review_count")),
            }
        )


def test_reject_invalid_r2_features():
    with pytest.raises(ValidationError, match="R2"):
        MLFreezeConfig(
            representations={
                "R1": FreezeRepresentation(features=("price", "rating")),
                "R2": FreezeRepresentation(features=("price", "rating")),
            }
        )


def test_reject_missing_r1_or_r2():
    with pytest.raises(ValidationError, match="R1"):
        MLFreezeConfig(
            representations={
                "R2": FreezeRepresentation(features=("price", "rating", "review_count")),
            }
        )

    with pytest.raises(ValidationError, match="R2"):
        MLFreezeConfig(
            representations={
                "R1": FreezeRepresentation(features=("price", "rating")),
            }
        )


def test_reject_allow_ambiguous_in_ml():
    with pytest.raises(ValidationError, match="allow_ambiguous_in_ml"):
        MLFreezeConfig(
            representations={
                "R1": FreezeRepresentation(features=("price", "rating")),
                "R2": FreezeRepresentation(features=("price", "rating", "review_count")),
            },
            eligibility=FreezeEligibilityConfig(allow_ambiguous_in_ml=True),
        )


def test_reject_invalid_default_missing_policy():
    with pytest.raises(ValidationError, match="default_missing_policy"):
        MLFreezeConfig(
            representations={
                "R1": FreezeRepresentation(features=("price", "rating")),
                "R2": FreezeRepresentation(features=("price", "rating", "review_count")),
            },
            review_count=FreezeReviewCountConfig(default_missing_policy="FILL_ZERO"),
        )


def test_load_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        load_ml_freeze_config("nonexistent_path/ml_freeze.yaml")


def test_enum_and_cleaning_decision_contracts():
    assert EligibilityDecision.VALID_LAPTOP == "VALID_LAPTOP"
    assert EligibilityDecision.EXCLUDE == "EXCLUDE"
    assert EligibilityDecision.AMBIGUOUS == "AMBIGUOUS"

    assert EligibilityReason.VALID_LAPTOP == "VALID_LAPTOP"
    assert EligibilityReason.NON_LAPTOP_ACCESSORY == "NON_LAPTOP_ACCESSORY"
    assert EligibilityReason.NON_LAPTOP_COMPONENT == "NON_LAPTOP_COMPONENT"
    assert EligibilityReason.NON_LAPTOP_OTHER == "NON_LAPTOP_OTHER"
    assert EligibilityReason.INVALID_PRICE_REPRESENTATION == "INVALID_PRICE_REPRESENTATION"
    assert EligibilityReason.DOWN_PAYMENT_OR_DEPOSIT == "DOWN_PAYMENT_OR_DEPOSIT"
    assert EligibilityReason.AMBIGUOUS_PRODUCT == "AMBIGUOUS_PRODUCT"

    assert ReviewCountSemanticStatus.OBSERVED_COUNT == "OBSERVED_COUNT"
    assert ReviewCountSemanticStatus.EXPLICIT_ZERO == "EXPLICIT_ZERO"
    assert ReviewCountSemanticStatus.SEMANTIC_ZERO_PROVEN == "SEMANTIC_ZERO_PROVEN"
    assert ReviewCountSemanticStatus.MISSING_UNRESOLVED == "MISSING_UNRESOLVED"

    decision = CleaningDecision(
        listing_key="test_listing",
        eligibility_decision=EligibilityDecision.VALID_LAPTOP,
        eligibility_reason=EligibilityReason.VALID_LAPTOP,
        review_count_status=ReviewCountSemanticStatus.OBSERVED_COUNT,
        include_r1=True,
        include_r2=True,
        exclusion_reasons_r1=(),
        exclusion_reasons_r2=(),
        evidence=("verified laptop name",),
    )
    assert decision.listing_key == "test_listing"
    assert decision.include_r1 is True
    assert decision.include_r2 is True
