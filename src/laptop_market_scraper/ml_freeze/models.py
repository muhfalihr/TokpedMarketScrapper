from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class EligibilityDecision(StrEnum):
    VALID_LAPTOP = "VALID_LAPTOP"
    EXCLUDE = "EXCLUDE"
    AMBIGUOUS = "AMBIGUOUS"


class EligibilityReason(StrEnum):
    VALID_LAPTOP = "VALID_LAPTOP"
    NON_LAPTOP_ACCESSORY = "NON_LAPTOP_ACCESSORY"
    NON_LAPTOP_COMPONENT = "NON_LAPTOP_COMPONENT"
    NON_LAPTOP_OTHER = "NON_LAPTOP_OTHER"
    INVALID_PRICE_REPRESENTATION = "INVALID_PRICE_REPRESENTATION"
    DOWN_PAYMENT_OR_DEPOSIT = "DOWN_PAYMENT_OR_DEPOSIT"
    AMBIGUOUS_PRODUCT = "AMBIGUOUS_PRODUCT"


class ProductHeadCategory(StrEnum):
    LAPTOP = "LAPTOP"
    COMPONENT = "COMPONENT"
    ACCESSORY = "ACCESSORY"
    PAPER_NOTEBOOK = "PAPER_NOTEBOOK"
    PLACEHOLDER = "PLACEHOLDER"
    UNKNOWN = "UNKNOWN"


class ProductHeadAssessment(BaseModel):
    category: ProductHeadCategory
    matched_phrase: str | None = None
    evidence: tuple[str, ...] = ()


class ReviewCountSemanticStatus(StrEnum):
    OBSERVED_COUNT = "OBSERVED_COUNT"
    EXPLICIT_ZERO = "EXPLICIT_ZERO"
    SEMANTIC_ZERO_PROVEN = "SEMANTIC_ZERO_PROVEN"
    MISSING_UNRESOLVED = "MISSING_UNRESOLVED"


class ManualReviewStatus(StrEnum):
    APPROVED_VALID = "APPROVED_VALID"
    LEAKAGE = "LEAKAGE"
    AMBIGUOUS = "AMBIGUOUS"


class LowPriceReviewDecision(BaseModel):
    listing_key: str
    review_status: ManualReviewStatus
    review_note: str

    @model_validator(mode="after")
    def validate_review_note(self) -> "LowPriceReviewDecision":
        if not self.review_note or not self.review_note.strip():
            raise ValueError("review_note must be a non-empty string")
        return self


class CleaningDecision(BaseModel):
    listing_key: str
    eligibility_decision: EligibilityDecision
    eligibility_reason: EligibilityReason
    review_count_status: ReviewCountSemanticStatus
    include_r1: bool
    include_r2: bool
    exclusion_reasons_r1: tuple[str, ...] = ()
    exclusion_reasons_r2: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


class FreezeRepresentation(BaseModel):
    features: tuple[str, ...]


class FreezeEligibilityConfig(BaseModel):
    allow_ambiguous_in_ml: bool = False
    accessory_terms: tuple[str, ...] = ()
    component_terms: tuple[str, ...] = ()
    invalid_price_terms: tuple[str, ...] = ()


class FreezeReviewCountConfig(BaseModel):
    default_missing_policy: str = "KEEP_MISSING"
    allow_semantic_zero_recode: bool = False


class FreezeOutputsConfig(BaseModel):
    include_identity_columns: tuple[str, ...] = (
        "listing_key",
        "product_name",
        "product_url",
    )


class MLFreezeConfig(BaseModel):
    version: str = "1.0"
    artifact_name: str = "ml-dataset-v1.0"
    representations: dict[str, FreezeRepresentation]
    eligibility: FreezeEligibilityConfig = Field(default_factory=FreezeEligibilityConfig)
    review_count: FreezeReviewCountConfig = Field(default_factory=FreezeReviewCountConfig)
    outputs: FreezeOutputsConfig = Field(default_factory=FreezeOutputsConfig)

    @model_validator(mode="after")
    def validate_freeze_contracts(self) -> "MLFreezeConfig":
        if "R1" not in self.representations:
            raise ValueError("MLFreezeConfig must define representation 'R1'")
        if self.representations["R1"].features != ("price", "rating"):
            raise ValueError(
                f"R1 representation features must be ('price', 'rating'), got {self.representations['R1'].features}"
            )

        if "R2" not in self.representations:
            raise ValueError("MLFreezeConfig must define representation 'R2'")
        if self.representations["R2"].features != ("price", "rating", "review_count"):
            raise ValueError(
                f"R2 representation features must be ('price', 'rating', 'review_count'), got {self.representations['R2'].features}"
            )

        if self.eligibility.allow_ambiguous_in_ml:
            raise ValueError("allow_ambiguous_in_ml must be False in locked freeze configuration")

        if self.review_count.default_missing_policy != "KEEP_MISSING":
            raise ValueError(
                f"default_missing_policy must be 'KEEP_MISSING', got '{self.review_count.default_missing_policy}'"
            )

        return self
