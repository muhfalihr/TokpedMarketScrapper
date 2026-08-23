import pandas as pd
import pytest

from laptop_market_scraper.ml_readiness import (
    IntegrityResult,
    ReadinessDataset,
    audit_dataset_integrity,
)


@pytest.fixture
def valid_products_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "listing_key": "k1",
                "price": 15000000.0,
                "rating": 4.5,
                "review_count": 20,
                "product_name": "Laptop A",
            },
            {
                "listing_key": "k2",
                "price": 25000000.0,
                "rating": 5.0,
                "review_count": 0,
                "product_name": "Laptop B",
            },
            {
                "listing_key": "k3",
                "price": 10000000.0,
                "rating": None,
                "review_count": None,
                "product_name": "Laptop C",
            },
        ]
    )


@pytest.fixture
def valid_raw_by_listing_key() -> dict[str, dict]:
    return {
        "k1": {"listing_key": "k1", "raw": "data1"},
        "k2": {"listing_key": "k2", "raw": "data2"},
        "k3": {"listing_key": "k3", "raw": "data3"},
    }


def test_audit_dataset_integrity_pass(valid_products_df: pd.DataFrame, valid_raw_by_listing_key: dict):
    dataset = ReadinessDataset(
        products=valid_products_df,
        provenance=pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key=valid_raw_by_listing_key,
    )
    result = audit_dataset_integrity(dataset)

    assert isinstance(result, IntegrityResult)
    assert result.passed is True
    assert result.normalized_rows == 3
    assert result.raw_rows == 3
    assert result.unique_normalized_keys == 3
    assert result.unique_raw_keys == 3
    assert result.duplicate_normalized_keys == ()
    assert result.orphan_normalized_records == 0
    assert result.orphan_raw_records == 0
    assert result.missing_required_columns == ()
    assert result.invalid_price_keys == ()
    assert result.invalid_rating_keys == ()
    assert result.invalid_review_count_keys == ()


def test_audit_dataset_integrity_missing_columns(valid_raw_by_listing_key: dict):
    df_missing = pd.DataFrame(
        [
            {"listing_key": "k1", "price": 1000.0},
        ]
    )
    dataset = ReadinessDataset(
        products=df_missing,
        provenance=pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key=valid_raw_by_listing_key,
    )
    result = audit_dataset_integrity(dataset)

    assert result.passed is False
    assert set(result.missing_required_columns) == {"rating", "review_count"}


def test_audit_dataset_integrity_duplicate_keys(valid_products_df: pd.DataFrame, valid_raw_by_listing_key: dict):
    df_dup = pd.concat(
        [
            valid_products_df,
            pd.DataFrame(
                [
                    {
                        "listing_key": "k1",
                        "price": 15000000.0,
                        "rating": 4.5,
                        "review_count": 20,
                        "product_name": "Laptop A Dup",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    dataset = ReadinessDataset(
        products=df_dup,
        provenance=pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key=valid_raw_by_listing_key,
    )
    result = audit_dataset_integrity(dataset)

    assert result.passed is False
    assert result.duplicate_normalized_keys == ("k1",)
    assert result.unique_normalized_keys == 3
    assert result.normalized_rows == 4


def test_audit_dataset_integrity_invalid_values(valid_raw_by_listing_key: dict):
    df_invalid = pd.DataFrame(
        [
            # invalid price (<=0)
            {"listing_key": "k1", "price": 0.0, "rating": 4.0, "review_count": 10},
            # invalid price (negative)
            {"listing_key": "k2", "price": -500.0, "rating": 4.0, "review_count": 10},
            # invalid rating (>5)
            {"listing_key": "k3", "price": 1000.0, "rating": 5.5, "review_count": 10},
            # invalid rating (<0)
            {"listing_key": "k4", "price": 1000.0, "rating": -1.0, "review_count": 10},
            # invalid review_count (<0)
            {"listing_key": "k5", "price": 1000.0, "rating": 4.0, "review_count": -5},
            # invalid price (non-numeric)
            {"listing_key": "k6", "price": "invalid_price", "rating": 4.0, "review_count": 10},
        ]
    )
    raw = {f"k{i}": {} for i in range(1, 7)}
    dataset = ReadinessDataset(
        products=df_invalid,
        provenance=pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key=raw,
    )
    result = audit_dataset_integrity(dataset)

    assert result.passed is False
    assert result.invalid_price_keys == ("k1", "k2", "k6")
    assert result.invalid_rating_keys == ("k3", "k4")
    assert result.invalid_review_count_keys == ("k5",)


def test_audit_dataset_integrity_orphans():
    products_df = pd.DataFrame(
        [
            {"listing_key": "k1", "price": 1000.0, "rating": 4.0, "review_count": 10},
            {"listing_key": "k2", "price": 2000.0, "rating": 4.0, "review_count": 10},
        ]
    )
    raw = {
        "k2": {},
        "k3": {},
    }
    dataset = ReadinessDataset(
        products=products_df,
        provenance=pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key=raw,
    )
    result = audit_dataset_integrity(dataset)

    assert result.orphan_normalized_records == 1  # k1 is not in raw
    assert result.orphan_raw_records == 1  # k3 is not in products
    assert result.passed is False
