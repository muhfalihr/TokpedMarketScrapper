"""K-Means clustering pipeline for Tokopedia laptop market data."""

from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_and_audit_data(csv_path: str | Path, features: list[str]) -> pd.DataFrame:
    """Load dataset from CSV and print a detailed audit of missing values."""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"Dataset file not found at: {csv_file.resolve()}")

    df = pd.read_csv(csv_file)

    print("=" * 60)
    print(f"Dataset Loaded : {csv_file.name}")
    print(f"Total Rows     : {len(df):,}")
    print("=" * 60)

    # Missing value audit
    missing_counts = df[features].isnull().sum()
    print("\n--- Ringkasan Missing Values pada Fitur ---")
    for col, count in missing_counts.items():
        pct = (count / len(df)) * 100 if len(df) > 0 else 0
        print(f"  - {col:<25}: {count:>5} baris null ({pct:>5.1f}%)")

    # Correct boolean indexing along rows (axis=1)
    missing_mask = df[features].isnull().any(axis=1)
    rows_with_null = df[missing_mask]
    print(f"\nTotal baris memiliki setidaknya 1 nilai null: {len(rows_with_null):,} baris")

    return df


def clean_dataset(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Filter valid laptop products and drop rows with missing values in clustering features."""
    initial_count = len(df)

    # Validate required columns
    missing_cols = [col for col in features if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Features missing from DataFrame: {missing_cols}")

    if "eligibility_decision" in df.columns:
        df_filtered = df[df["eligibility_decision"] == "VALID_LAPTOP"].copy()
        excluded_count = initial_count - len(df_filtered)
    else:
        df_filtered = df.copy()
        excluded_count = 0

    # Complete Cases: drop rows containing nulls in selected features
    df_clean = df_filtered.dropna(subset=features).copy()
    dropped_null_count = len(df_filtered) - len(df_clean)

    if len(df_clean) == 0:
        raise ValueError("No valid rows remaining after data cleaning.")

    print("\n" + "=" * 60)
    print("--- Log Pembersihan Data (Data Cleaning Audit) ---")
    print(f"  Baris Awal             : {initial_count:>6,}")
    print(f"  Disaring (Non-Laptop)  : -{excluded_count:>5,}")
    print(f"  Dibuang (Nilai Null)   : -{dropped_null_count:>5,}")
    print(f"  Total Data Bersih      :  {len(df_clean):>5,} (Siap untuk K-Means)")
    print("=" * 60)

    return df_clean
