from pathlib import Path
import pandas as pd
import pytest

from scripts.k_mean import load_and_audit_data, clean_dataset


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    return pd.DataFrame({
        "listing_key": ["k1", "k2", "k3", "k4", "k5"],
        "product_name": ["Laptop A", "Laptop B (no rating)", "Charger X", "Laptop C (no review)", "Laptop D"],
        "price": [10000000, 12000000, 500000, 8000000, 15000000],
        "rating": [4.8, None, 5.0, 4.2, 4.9],
        "review_count_resolved": [25.0, 10.0, 100.0, None, 14.0],
        "eligibility_decision": ["VALID_LAPTOP", "VALID_LAPTOP", "EXCLUDE", "VALID_LAPTOP", "VALID_LAPTOP"]
    })


def test_clean_dataset_filters_ineligible_and_nulls(sample_raw_df: pd.DataFrame):
    features = ["price", "rating", "review_count_resolved"]
    cleaned_df = clean_dataset(sample_raw_df, features)

    # k1 and k5 are the only valid laptops with complete features
    assert len(cleaned_df) == 2
    assert set(cleaned_df["listing_key"]) == {"k1", "k5"}
    assert cleaned_df[features].isnull().sum().sum() == 0


def test_clean_dataset_raises_on_empty_result():
    empty_df = pd.DataFrame({
        "price": [],
        "rating": [],
        "review_count_resolved": [],
        "eligibility_decision": []
    })
    features = ["price", "rating", "review_count_resolved"]
    with pytest.raises(ValueError, match="No valid rows remaining"):
        clean_dataset(empty_df, features)


def test_load_and_audit_data_file_not_found(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.csv"
    with pytest.raises(FileNotFoundError):
        load_and_audit_data(non_existent, ["price", "rating"])
