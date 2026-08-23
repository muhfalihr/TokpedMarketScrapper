"""Semantic eligibility reconciliation for ML dataset freeze.

Classifies products as VALID_LAPTOP, EXCLUDE, or AMBIGUOUS based on
title semantics and raw evidence — never on price magnitude alone.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from laptop_market_scraper.ml_freeze.models import (
    EligibilityDecision,
    EligibilityReason,
    MLFreezeConfig,
)


class EligibilityAssessment(BaseModel):
    listing_key: str
    decision: EligibilityDecision
    reason: EligibilityReason
    evidence: tuple[str, ...] = ()


def _normalize_title(title: str) -> str:
    """Lowercase and normalize whitespace for matching."""
    return re.sub(r"\s+", " ", title.lower().strip())


def _has_any_term(text: str, terms: tuple[str, ...]) -> str | None:
    """Check if any term appears in text. Returns the matched term or None."""
    for term in terms:
        if term.lower() in text:
            return term
    return None


def _is_component_by_title(title: str, config: MLFreezeConfig) -> str | None:
    """Check if title indicates a laptop component (not a full laptop)."""
    normalized = _normalize_title(title)
    return _has_any_term(normalized, config.eligibility.component_terms)


def _is_accessory_by_title(title: str, config: MLFreezeConfig) -> str | None:
    """Check if title indicates a laptop accessory."""
    normalized = _normalize_title(title)
    return _has_any_term(normalized, config.eligibility.accessory_terms)


def _is_invalid_price_representation(title: str, config: MLFreezeConfig) -> str | None:
    """Check if title indicates a non-full-product price (DP, deposit, etc.)."""
    normalized = _normalize_title(title)

    # Check for DP as a standalone word at start of title
    if re.match(r"^dp\b", normalized):
        return "dp"

    return _has_any_term(normalized, config.eligibility.invalid_price_terms)


def assess_ml_eligibility(
    *,
    row: Mapping[str, Any],
    raw: Mapping[str, Any] | None,
    config: MLFreezeConfig,
) -> EligibilityAssessment:
    """Assess whether a product is eligible for ML dataset inclusion.

    Uses semantic evidence from title and raw data — never price magnitude alone.

    Returns an EligibilityAssessment with decision, reason, and evidence.
    """
    listing_key = str(row.get("listing_key", ""))
    title = str(row.get("product_name", ""))
    evidence: list[str] = []

    # Priority 1: Check for component (LCD, keyboard, cable, shell, etc.)
    component_match = _is_component_by_title(title, config)
    if component_match:
        evidence.append(f"title contains component term '{component_match}'")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_COMPONENT,
            evidence=tuple(evidence),
        )

    # Priority 2: Check for accessory (charger, sleeve, stand, etc.)
    accessory_match = _is_accessory_by_title(title, config)
    if accessory_match:
        evidence.append(f"title contains accessory term '{accessory_match}'")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_ACCESSORY,
            evidence=tuple(evidence),
        )

    # Priority 3: Check for invalid price representation (DP, deposit, etc.)
    price_match = _is_invalid_price_representation(title, config)
    if price_match:
        evidence.append(f"title contains invalid price term '{price_match}'")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.DOWN_PAYMENT_OR_DEPOSIT,
            evidence=tuple(evidence),
        )

    # Priority 4: Check raw evidence for invalid price terms in variants
    if raw:
        raw_str = str(raw).lower()
        for term in config.eligibility.invalid_price_terms:
            if term.lower() in raw_str and term.lower() not in _normalize_title(title):
                evidence.append(f"raw data contains invalid price term '{term}'")
                return EligibilityAssessment(
                    listing_key=listing_key,
                    decision=EligibilityDecision.EXCLUDE,
                    reason=EligibilityReason.INVALID_PRICE_REPRESENTATION,
                    evidence=tuple(evidence),
                )

    # Default: valid laptop
    evidence.append("no exclusion evidence found")
    return EligibilityAssessment(
        listing_key=listing_key,
        decision=EligibilityDecision.VALID_LAPTOP,
        reason=EligibilityReason.VALID_LAPTOP,
        evidence=tuple(evidence),
    )
