from enum import Enum
from typing import Literal

from pydantic import BaseModel


class ReliabilityStatus(str, Enum):
    VERIFIED_EXACT = "VERIFIED_EXACT"
    VERIFIED_APPROXIMATE = "VERIFIED_APPROXIMATE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    SEMANTICS_UNVERIFIED = "SEMANTICS_UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"


class FeatureRegistryEntry(BaseModel):
    feature_name: str
    research_dimension: Literal["Pricing", "Demand", "Engagement", "Perception"]
    expected_dtype: str
    nullable: bool
    semantic_description: str
    known_semantic_limitations: str
    default_reliability: ReliabilityStatus
