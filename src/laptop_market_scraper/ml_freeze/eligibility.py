"""Semantic eligibility reconciliation for ML dataset freeze.

Classifies products as VALID_LAPTOP, EXCLUDE, or AMBIGUOUS based on
title semantics and raw evidence — never on price magnitude alone.
Uses boundary-aware and context-aware lexical matchers to prevent false positives.
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


# --- Regex rules for Lexical & Context Boundaries ---

# Match standalone 'dp' (not in ADP, 2ADP, 3ADP, NX.DPESN, etc.)
DP_TOKEN_RE = re.compile(r"(?<![a-z0-9])dp(?![a-z0-9])", re.IGNORECASE)

# Match 'shell' as a standalone word (not in Seashell)
SHELL_TOKEN_RE = re.compile(r"(?<![a-z0-9])shell(?![a-z0-9])", re.IGNORECASE)

# Match 'sleeve' as a standalone word
SLEEVE_TOKEN_RE = re.compile(r"(?<![a-z0-9])sleeve(?![a-z0-9])", re.IGNORECASE)

# Match 'keyboard' / 'keyborad' / 'keyboad'
KEYBOARD_TOKEN_RE = re.compile(r"(?<![a-z0-9])(keyboard|keyborad|keyboad)(?![a-z0-9])", re.IGNORECASE)

# Match 'lcd'
LCD_TOKEN_RE = re.compile(r"(?<![a-z0-9])lcd(?![a-z0-9])", re.IGNORECASE)


# --- Laptop Identity Indicators ---
LAPTOP_BRAND_MODEL_RE = re.compile(
    r"\b(laptop|notebook|macbook|ultrabook|vivobook|zenbook|ideapad|thinkpad|yoga|"
    r"legion|loq|expertbook|rog|tuf|predator|nitro|aspire|swift|spin|travelmate|"
    r"pavilion|envy|spectre|omen|victus|latitude|inspiron|vostro|xps|alienware|"
    r"thinkbook|matebook|gram|razer|galaxy book)\b",
    re.IGNORECASE,
)


def has_strong_laptop_identity(title: str) -> bool:
    """Check if title contains clear laptop brand/series/category keywords."""
    return bool(LAPTOP_BRAND_MODEL_RE.search(title))


# --- Invalid Price Semantics ---


def contains_invalid_price_semantics(text: str) -> tuple[bool, str | None]:
    """Check if text contains explicit invalid-price terms (DP, down payment, deposit, etc.).

    Returns (matched: bool, match_term: str | None).
    """
    normalized = _normalize_title(text)

    # Standalone DP token (e.g., "DP Laptop...", "DP - Laptop...")
    if DP_TOKEN_RE.search(normalized):
        # Exclude ADP / 2ADP / 3ADP / DPESN which are caught by negative lookbehind/lookahead
        return True, "dp"

    # Multi-word invalid price phrases
    phrases = ["down payment", "uang muka", "deposit", "cicilan"]
    for phrase in phrases:
        pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
        if re.search(pattern, normalized):
            return True, phrase

    return False, None


# --- Component Semantics ---


def contains_component_semantics(title: str, config: MLFreezeConfig) -> tuple[bool, str | None]:
    """Check if title indicates a standalone laptop component (not a full laptop)."""
    normalized = _normalize_title(title)
    is_laptop = has_strong_laptop_identity(title)

    # 1. Shell component check (e.g. "Laptop Shell For...", "Replacement Shell")
    if SHELL_TOKEN_RE.search(normalized):
        # "Seashell" color is excluded by token boundary
        if re.search(r"\b(laptop shell|shell for|replacement shell|casing)\b", normalized):
            return True, "shell"
        if not is_laptop:
            return True, "shell"

    # 2. Keyboard component check (e.g. "Keyboard Docking", "Keyboard Laptop ThinkPad T430")
    if KEYBOARD_TOKEN_RE.search(normalized):
        # Explicit component phrases (always exclude, regardless of target laptop model)
        if re.search(
            r"\b(keyboard docking|keyboard replacement|keyboard laptop|keyboard for|keyborad laptop|docking keyboard)\b",
            normalized,
        ):
            return True, "keyboard"
        # If title starts with Keyboard / Keyborad (e.g. "Keyboard Lenovo...")
        if re.match(r"^\s*keybor?ad\b", normalized) and not re.search(r"\b(backlit|rgb)\b", normalized):
            return True, "keyboard"
        # If NOT strong laptop identity and contains keyboard
        if not is_laptop and not re.search(r"\b(backlit|rgb)\b", normalized):
            return True, "keyboard"

    # 3. LCD component check (e.g. "LCD LED HP...", "LCD Laptop...", "Replacement LCD")
    if LCD_TOKEN_RE.search(normalized):
        # Check for LCD replacement panel phrases
        if re.search(
            r"\b(lcd led|lcd laptop|layar lcd|replacement lcd|panel lcd|lcd screen replacement)\b",
            normalized,
        ):
            return True, "lcd"
        # If title starts with LCD / Layar LCD (e.g. "LCD LED HP Ultrabook...")
        if re.match(r"^\s*(lcd|layar lcd)\b", normalized):
            return True, "lcd"
        # If NOT strong laptop identity and contains lcd
        if not is_laptop and not re.search(r"\b(touch|display|screen)\b", normalized):
            return True, "lcd"

    # 4. Other explicit component terms
    other_components = [
        "kabel fleksibel",
        "flex cable",
        "sparepart",
        "spare part",
        "baterai laptop",
    ]
    for term in other_components:
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        if re.search(pattern, normalized):
            return True, term

    return False, None


# --- Accessory Semantics ---


def contains_accessory_semantics(title: str, config: MLFreezeConfig) -> tuple[bool, str | None]:
    """Check if title indicates a standalone laptop accessory (not a full laptop bundle)."""
    normalized = _normalize_title(title)
    is_laptop = has_strong_laptop_identity(title)

    # 1. Sleeve accessory check
    if SLEEVE_TOKEN_RE.search(normalized) or "sleevecase" in normalized:
        # Bundle context (+ sleeve, bonus sleeve, free sleeve, include sleeve) on a valid laptop
        if is_laptop and re.search(r"(\+|\bbonus\b|\bfree\b|\binclude\b|\bwith\b)\s*sleeve", normalized):
            return False, None
        if is_laptop and re.search(r"sleeve\s*(\bbonus\b|\bfree\b|\binclude\b)", normalized):
            return False, None
        # Standalone sleeve product (e.g. "Sleevecase Laptop...", "Acer Sleevecase...", "Sleeve Laptop 14 inch")
        if re.search(
            r"\b(sleevecase|sleeve case|sleeve laptop|sleeve for|laptop sleeve)\b",
            normalized,
        ):
            return True, "sleeve"
        if not is_laptop:
            return True, "sleeve"

    # 2. Other standalone accessories (charger, adaptor, stand laptop, stiker, etc.)
    standalone_accessories = [
        "charger",
        "adaptor",
        "adapter",
        "tas laptop",
        "cooling pad",
        "stand laptop",
        "stiker",
        "sticker",
    ]
    for term in standalone_accessories:
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        if re.search(pattern, normalized) and (
            not is_laptop
            or re.match(rf"^\s*{re.escape(term)}\b", normalized)
            or re.search(rf"\b{re.escape(term)}\s+(laptop|for)\b", normalized)
        ):
            return True, term

    return False, None


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

    # Priority 1: Check for invalid price representation (DP, down payment, deposit, etc.)
    has_invalid_price, price_term = contains_invalid_price_semantics(title)
    if has_invalid_price:
        evidence.append(f"title contains invalid price term '{price_term}'")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.DOWN_PAYMENT_OR_DEPOSIT,
            evidence=tuple(evidence),
        )

    # Priority 2: Check for component (LCD, keyboard, cable, shell, etc.)
    has_component, comp_term = contains_component_semantics(title, config)
    if has_component:
        evidence.append(f"title contains component term '{comp_term}'")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_COMPONENT,
            evidence=tuple(evidence),
        )

    # Priority 3: Check for accessory (charger, sleeve, stand, etc.)
    has_accessory, acc_term = contains_accessory_semantics(title, config)
    if has_accessory:
        evidence.append(f"title contains accessory term '{acc_term}'")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_ACCESSORY,
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
