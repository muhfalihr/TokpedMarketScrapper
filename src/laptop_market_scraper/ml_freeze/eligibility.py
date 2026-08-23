"""Semantic eligibility reconciliation for ML dataset freeze.

Classifies products as VALID_LAPTOP, EXCLUDE, or AMBIGUOUS based on
title semantics and raw evidence — never on price magnitude alone.
Uses boundary-aware and context-aware lexical matchers to prevent false positives and false negatives.
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
    ProductHeadAssessment,
    ProductHeadCategory,
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


# --- Product Head Classifier ---


def classify_product_head(title: str) -> ProductHeadAssessment:
    """Classify the primary product identity (product head) being sold from title.

    Determines if title primary product is LAPTOP, COMPONENT, ACCESSORY,
    PAPER_NOTEBOOK, PLACEHOLDER, or UNKNOWN without using price.
    """
    normalized = _normalize_title(title)

    # 1. Paper Notebook Check
    if re.search(r"\bnotebook\s+a[34567]\b", normalized) or re.search(
        r"\b(buku notebook|notebook spiral|notebook paper|notebook binder|notebook tulis)\b",
        normalized,
    ):
        return ProductHeadAssessment(
            category=ProductHeadCategory.PAPER_NOTEBOOK,
            matched_phrase="paper notebook title pattern",
            evidence=("title indicates paper stationery notebook",),
        )

    # 2. Placeholder / Bonus Check
    if re.search(r"^\s*(\[\s*new\s*\]\s*)?(bonus|hadiah)\s+(pembelian|untuk)", normalized) or re.search(
        r"\b(bubble wrap|screen protector keyboard protector|keyboard protector screen protector|macbook air & macbook pro office|macbook air macbook pro office)\b",
        normalized,
    ):
        return ProductHeadAssessment(
            category=ProductHeadCategory.PLACEHOLDER,
            matched_phrase="bonus/placeholder title pattern",
            evidence=("title indicates bonus placeholder listing",),
        )

    # 3. Power Accessory / Cable / Adapter / Charger Check
    if (
        re.search(r"\bkabel\s+power\b", normalized)
        or re.search(r"\bpower\s+adapto?r\b", normalized)
        or re.search(r"^\s*(charger|adaptor|adapter|ac\s+plugin|plugin\s+port)\b", normalized)
        or re.search(r"\b(charger|adaptor|adapter|ac\s+plugin)\s+(laptop|notebook|for|indonesia|macbook)\b", normalized)
    ) and not (
        has_strong_laptop_identity(title)
        and re.search(r"\b(included|free|bonus|with)\b", normalized)
        and not re.search(r"^\s*(kabel|power|charger|adaptor|adapter|ac\s+plugin)\b", normalized)
    ):
        return ProductHeadAssessment(
            category=ProductHeadCategory.ACCESSORY,
            matched_phrase="power cable/adapter/charger product head",
            evidence=("title indicates power accessory product head",),
        )

    # 4. Memory / Storage / Battery / Motherboard Component Check
    if (
        re.search(r"^\s*(ram|sodimm|memory|motherboard|mobo|mainboard)\b", normalized)
        or (
            re.search(r"\b(ram laptop|ram notebook|sodimm ddr)\b", normalized)
            and not re.search(r"\b\d+\s*gb\s+ram\s+(laptop|notebook)\b", normalized)
        )
        or re.search(r"\b(motherboard|mobo|mainboard)\b", normalized)
        or re.search(r"^\s*ssd\b", normalized)
        or re.search(r"\bssd\s+(toshiba|samsung|v-gen|kingston|adata|lexar|crucial|wd)\b", normalized)
        or re.search(r"^\s*(baterai|battery)\b", normalized)
        or re.search(r"\b(baterai|battery)\s+(battery|laptop|notebook|ultrabook|dell|lenovo|asus|hp|acer|macbook)\b", normalized)
        or re.search(r"\b(hdd|hard disk|harddisk)\s+(laptop|notebook)\b", normalized)
    ) and not (
        has_strong_laptop_identity(title)
        and re.search(r"^\s*(laptop|notebook|ultrabook|macbook|asus|lenovo|hp|dell|acer|msi|thinkpad|ideapad)\b", normalized)
        and not re.search(r"^\s*(ram|sodimm|ssd|baterai|battery|hdd|motherboard|mobo|mainboard)\b", normalized)
    ):
        return ProductHeadAssessment(
            category=ProductHeadCategory.COMPONENT,
            matched_phrase="memory/storage/battery/motherboard component product head",
            evidence=("title indicates component product head",),
        )

    # 5. Display / Bracket / Connector / Flex Cable Component Check
    if (
        re.search(r"^\s*(led lcd|layar lcd|panel lcd|lcd led|lcd|led)\s+\d", normalized)
        or re.search(r"^\s*(led lcd|layar lcd|panel lcd|lcd led|lcd)\b", normalized)
        or re.search(r"\b(layar lcd|panel lcd|lcd led)\b", normalized)
        or re.search(r"\b(bracket|frame)\s+(hdd|ssd)\b", normalized)
        or re.search(r"\b(konektor|connector)\s+(fleksibel|flex)\b", normalized)
        or re.search(r"\b(kabel fleksibel|flex cable)\b", normalized)
    ) and not (
        has_strong_laptop_identity(title)
        and re.search(r"\b(touch|display|screen|ips|fhd|wuxga|oled)\b", normalized)
        and not re.search(r"^\s*(led lcd|layar lcd|panel lcd|lcd led|konektor|kabel fleksibel|bracket|led\s+\d)\b", normalized)
    ):
        return ProductHeadAssessment(
            category=ProductHeadCategory.COMPONENT,
            matched_phrase="display/connector component product head",
            evidence=("title indicates display/connector component product head",),
        )

    # 6. Security Lock / Protector / Casing / Shell / Armor Case Check
    if (
        re.search(r"\b(security lock|kunci gembok|kunci laptop|gembok laptop|notebook lock)\b", normalized)
        or re.search(r"\b(screen protector|keyboard protector)\b", normalized)
        or re.search(r"^\s*(casing|shell|armor case|case for)\b", normalized)
        or re.search(r"\b(casing notebook|casing laptop|laptop shell|shell for|armor case|case for macbook|case for laptop)\b", normalized)
    ) and not (
        has_strong_laptop_identity(title)
        and re.search(r"^\s*(laptop|notebook|ultrabook|macbook|asus|lenovo|hp|dell|acer|msi|thinkpad|ideapad)\b", normalized)
        and not re.search(r"^\s*(security lock|kunci|screen protector|keyboard protector|casing|shell|armor case)\b", normalized)
    ):
        category = ProductHeadCategory.ACCESSORY if re.search(r"\b(lock|protector|case)\b", normalized) else ProductHeadCategory.COMPONENT
        return ProductHeadAssessment(
            category=category,
            matched_phrase="lock/protector/casing product head",
            evidence=("title indicates lock/protector/casing product head",),
        )

    # 7. Strong Laptop Check
    if has_strong_laptop_identity(title):
        return ProductHeadAssessment(
            category=ProductHeadCategory.LAPTOP,
            matched_phrase="laptop brand/model identity",
            evidence=("title indicates laptop product head",),
        )

    return ProductHeadAssessment(
        category=ProductHeadCategory.UNKNOWN,
        matched_phrase=None,
        evidence=("insufficient title evidence for product head",),
    )


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
        if re.search(r"\b(laptop shell|shell for|replacement shell|casing)\b", normalized):
            return True, "shell"
        if not is_laptop:
            return True, "shell"

    # 2. Keyboard component check (e.g. "Keyboard Docking", "Keyboard Laptop ThinkPad T430")
    if KEYBOARD_TOKEN_RE.search(normalized):
        if re.search(
            r"\b(keyboard docking|keyboard replacement|keyboard laptop|keyboard for|keyborad laptop|docking keyboard)\b",
            normalized,
        ):
            return True, "keyboard"
        if re.match(r"^\s*keybor?ad\b", normalized) and not re.search(r"\b(backlit|rgb)\b", normalized):
            return True, "keyboard"
        if not is_laptop and not re.search(r"\b(backlit|rgb)\b", normalized):
            return True, "keyboard"

    # 3. LCD component check (e.g. "LCD LED HP...", "LCD Laptop...", "Replacement LCD")
    if LCD_TOKEN_RE.search(normalized):
        if re.search(
            r"\b(lcd led|lcd laptop|layar lcd|replacement lcd|panel lcd|lcd screen replacement)\b",
            normalized,
        ):
            return True, "lcd"
        if re.match(r"^\s*(lcd|layar lcd)\b", normalized):
            return True, "lcd"
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
        if is_laptop and re.search(r"(\+|\bbonus\b|\bfree\b|\binclude\b|\bwith\b)\s*sleeve", normalized):
            return False, None
        if is_laptop and re.search(r"sleeve\s*(\bbonus\b|\bfree\b|\binclude\b)", normalized):
            return False, None
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

    # Priority 2: Product Head Classification
    head_assessment = classify_product_head(title)
    if head_assessment.category == ProductHeadCategory.PAPER_NOTEBOOK:
        evidence.append(f"product head is PAPER_NOTEBOOK ({head_assessment.matched_phrase})")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_OTHER,
            evidence=tuple(evidence),
        )
    elif head_assessment.category == ProductHeadCategory.PLACEHOLDER:
        evidence.append(f"product head is PLACEHOLDER ({head_assessment.matched_phrase})")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_ACCESSORY,
            evidence=tuple(evidence),
        )
    elif head_assessment.category == ProductHeadCategory.COMPONENT:
        evidence.append(f"product head is COMPONENT ({head_assessment.matched_phrase})")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_COMPONENT,
            evidence=tuple(evidence),
        )
    elif head_assessment.category == ProductHeadCategory.ACCESSORY:
        evidence.append(f"product head is ACCESSORY ({head_assessment.matched_phrase})")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_ACCESSORY,
            evidence=tuple(evidence),
        )

    # Priority 3: Check for component (LCD, keyboard, cable, shell, etc.)
    has_component, comp_term = contains_component_semantics(title, config)
    if has_component:
        evidence.append(f"title contains component term '{comp_term}'")
        return EligibilityAssessment(
            listing_key=listing_key,
            decision=EligibilityDecision.EXCLUDE,
            reason=EligibilityReason.NON_LAPTOP_COMPONENT,
            evidence=tuple(evidence),
        )

    # Priority 4: Check for accessory (charger, sleeve, stand, etc.)
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
