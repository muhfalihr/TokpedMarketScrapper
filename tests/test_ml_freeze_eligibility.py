"""Tests for ML freeze eligibility reconciliation (Tasks 3 & 4)."""

import pytest

from tokped_market_scrapper.ml_freeze.config import load_ml_freeze_config
from tokped_market_scrapper.ml_freeze.eligibility import (
    EligibilityAssessment,
    assess_ml_eligibility,
)
from tokped_market_scrapper.ml_freeze.models import EligibilityDecision, EligibilityReason

_CONFIG = load_ml_freeze_config("config/ml_freeze.yaml")


def _assess(title: str, price: int = 10_000_000, listing_key: str = "test") -> EligibilityAssessment:
    row = {"listing_key": listing_key, "product_name": title, "price": price}
    return assess_ml_eligibility(row=row, raw=None, config=_CONFIG)


# --- Task 3: Known leakage regression ---


@pytest.mark.parametrize(
    ("title", "expected_reason"),
    [
        (
            "LCD LED HP Ultrabook 14-B HD",
            EligibilityReason.NON_LAPTOP_COMPONENT,
        ),
        (
            "Keyboard Docking Lenovo Thinkpad Helix Ultrabook Gen2",
            EligibilityReason.NON_LAPTOP_COMPONENT,
        ),
        (
            "Kabel Fleksibel LCD Acer Ultrabook S3-951",
            EligibilityReason.NON_LAPTOP_COMPONENT,
        ),
        (
            "Laptop Shell For Lenovo Thinkpad Helix Ultrabook",
            EligibilityReason.NON_LAPTOP_COMPONENT,
        ),
    ],
)
def test_known_accessory_leakage_is_excluded(title, expected_reason):
    result = _assess(title)
    assert result.decision == EligibilityDecision.EXCLUDE
    assert result.reason == expected_reason


def test_real_high_end_laptop_is_not_rejected_by_price():
    result = _assess("Acer Predator Helios 18 AI RTX 5090", price=189_999_008)
    assert result.decision != EligibilityDecision.EXCLUDE


def test_low_price_alone_cannot_exclude_product():
    result = _assess("Lenovo ThinkPad X260 Laptop Second", price=1_500_000)
    assert result.reason not in {
        EligibilityReason.INVALID_PRICE_REPRESENTATION,
        EligibilityReason.DOWN_PAYMENT_OR_DEPOSIT,
    }


# --- Task 4: Invalid price representation ---


@pytest.mark.parametrize(
    "title",
    [
        "DP Laptop Lenovo ThinkPad X1 Carbon",
        "Down Payment Macbook Pro M3",
        "Uang Muka Laptop Gaming ASUS ROG",
        "Deposit Notebook Acer Swift",
    ],
)
def test_down_payment_price_is_excluded(title):
    result = _assess(title, price=100_000)
    assert result.decision == EligibilityDecision.EXCLUDE
    assert result.reason == EligibilityReason.DOWN_PAYMENT_OR_DEPOSIT


def test_100m_laptop_is_not_invalid_price_by_magnitude():
    result = _assess("ASUS ROG STRIX SCAR 16 RTX5090 Laptop Gaming", price=105_598_896)
    assert result.reason != EligibilityReason.INVALID_PRICE_REPRESENTATION


# --- Task 13: Fixture-driven regression ---


def test_charger_is_accessory():
    result = _assess("Charger Laptop Lenovo 65W USB-C")
    assert result.decision == EligibilityDecision.EXCLUDE
    assert result.reason == EligibilityReason.NON_LAPTOP_ACCESSORY


def test_sleeve_is_accessory():
    result = _assess("Sleeve Laptop 14 inch Premium Leather")
    assert result.decision == EligibilityDecision.EXCLUDE
    assert result.reason == EligibilityReason.NON_LAPTOP_ACCESSORY


def test_sparepart_is_component():
    result = _assess("Sparepart Baterai Laptop Asus X455L")
    assert result.decision == EligibilityDecision.EXCLUDE
    assert result.reason == EligibilityReason.NON_LAPTOP_COMPONENT


def test_valid_laptop_passes():
    result = _assess("ASUS VivoBook 14 A1404VA Core i5 Laptop")
    assert result.decision == EligibilityDecision.VALID_LAPTOP
    assert result.reason == EligibilityReason.VALID_LAPTOP


def test_real_audit_examples_have_expected_semantic_decisions():
    import json
    from pathlib import Path

    fixture_path = Path("tests/fixtures/ml_freeze/semantic_cases.json")
    with open(fixture_path, encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        title = case["product_name"]
        price = case.get("price", 10_000_000)
        expected = case["expected"]

        result = _assess(title, price=price)
        assert result.decision.value == expected, f"Failed for '{title}'"


def load_fixture_cases(name: str) -> list[dict]:
    import json
    from pathlib import Path

    path = Path("tests/fixtures/ml_freeze") / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "case",
    load_fixture_cases("semantic_false_positive_cases.json"),
    ids=lambda c: c["case_id"],
)
def test_semantic_false_positive_cases_must_be_valid_laptops(case):
    result = _assess(case["product_name"], price=case.get("price", 10_000_000))
    assert result.decision == EligibilityDecision.VALID_LAPTOP, (
        f"Case '{case['case_id']}' failed: expected VALID_LAPTOP, got {result.decision} ({result.reason})"
    )


@pytest.mark.parametrize(
    "case",
    load_fixture_cases("semantic_true_positive_cases.json"),
    ids=lambda c: c["case_id"],
)
def test_semantic_true_positive_cases_must_be_excluded(case):
    result = _assess(case["product_name"], price=case.get("price", 500_000))
    assert result.decision == EligibilityDecision.EXCLUDE, (
        f"Case '{case['case_id']}' failed: expected EXCLUDE, got {result.decision}"
    )
    assert result.reason.value == case["expected_reason"], (
        f"Case '{case['case_id']}' failed: expected reason {case['expected_reason']}, got {result.reason.value}"
    )


@pytest.mark.parametrize(
    "case",
    load_fixture_cases("product_head_false_negative_cases.json"),
    ids=lambda c: c["case_id"],
)
def test_known_false_negative_is_excluded(case):
    result = _assess(case["product_name"], price=case.get("price", 500_000))
    assert result.decision == EligibilityDecision.EXCLUDE, (
        f"False negative case '{case['case_id']}' failed: expected EXCLUDE, got {result.decision}"
    )
    assert result.reason.value == case["expected_reason"], (
        f"False negative case '{case['case_id']}' failed: expected reason {case['expected_reason']}, got {result.reason.value}"
    )


@pytest.mark.parametrize(
    "case",
    load_fixture_cases("product_head_valid_laptop_controls.json"),
    ids=lambda c: c["case_id"],
)
def test_product_head_hardening_preserves_valid_laptops(case):
    result = _assess(case["product_name"], price=case.get("price", 10_000_000))
    assert result.decision == EligibilityDecision.VALID_LAPTOP, (
        f"Valid control case '{case['case_id']}' failed: expected VALID_LAPTOP, got {result.decision} ({result.reason})"
    )


def test_low_price_review_threshold_cannot_exclude_valid_laptop():
    result = _assess("Laptop ThinkPad X250 Second Core i5", price=1_500_000)
    assert result.decision == EligibilityDecision.VALID_LAPTOP




