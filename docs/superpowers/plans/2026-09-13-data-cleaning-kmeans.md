# Data Cleaning & K-Means Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `scripts/k_mean.py` into a robust, modular pipeline that cleans CSV null data, filters valid laptops, scales features, fits K-Means, prints audit statistics, and exports clustered data.

**Architecture:** Modular functional pipeline in `scripts/k_mean.py` (`load_and_audit_data` -> `clean_dataset` -> `run_kmeans_clustering` -> `report_and_export`) backed by pytest unit tests.

**Tech Stack:** Python, pandas, scikit-learn, pytest.

## Global Constraints

- Python compatibility: 3.10+ (current environment is Python 3.13)
- Features: strictly `["price", "rating", "review_count_resolved"]`
- Missing value policy: Complete Cases (`dropna(subset=features)`)
- Eligibility policy: preserve only `eligibility_decision == "VALID_LAPTOP"`
- K-Means parameters: `n_clusters=3`, `random_state=42`, `n_init="auto"`
- Default dataset input: `kaggle/release/v1.0.3/cleaning_decisions.csv`
- Default export output: `kaggle/release/v1.0.3/clustered_laptops.csv`

---

### Task 1: Core Data Cleaning & Audit Functions

**Files:**
- Modify: `scripts/k_mean.py`
- Create: `tests/test_k_mean_cleaning.py`

**Interfaces:**
- Produces:
  - `load_and_audit_data(csv_path: str | Path, features: list[str]) -> pd.DataFrame`
  - `clean_dataset(df: pd.DataFrame, features: list[str]) -> pd.DataFrame`

- [ ] **Step 1: Write failing unit tests for data loading, auditing, and cleaning**

Create `tests/test_k_mean_cleaning.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_k_mean_cleaning.py -v`  
Expected: FAIL (cannot import `load_and_audit_data` / `clean_dataset`)

- [ ] **Step 3: Implement `load_and_audit_data` and `clean_dataset` in `scripts/k_mean.py`**

Edit `scripts/k_mean.py`:
```python
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
    print(f"Dataset Loaded: {csv_file.name}")
    print(f"Total Rows: {len(df):,}")
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
    required_cols = list(features)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_k_mean_cleaning.py -v`  
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add scripts/k_mean.py tests/test_k_mean_cleaning.py
git commit -m "feat: add data loading and cleaning functions to k_mean.py with tests"
```

---

### Task 2: Clustering, Reporting, & Export Functions

**Files:**
- Modify: `scripts/k_mean.py`
- Create: `tests/test_k_mean_clustering.py`

**Interfaces:**
- Consumes:
  - `clean_dataset(df: pd.DataFrame, features: list[str]) -> pd.DataFrame`
- Produces:
  - `run_kmeans_clustering(df: pd.DataFrame, features: list[str], n_clusters: int = 3, random_state: int = 42) -> pd.DataFrame`
  - `report_and_export(df: pd.DataFrame, features: list[str], output_path: str | Path) -> None`
  - `main() -> None`

- [ ] **Step 1: Write failing unit tests for clustering, reporting, and export**

Create `tests/test_k_mean_clustering.py`:
```python
from pathlib import Path
import pandas as pd
import pytest

from scripts.k_mean import run_kmeans_clustering, report_and_export


@pytest.fixture
def sample_clean_df() -> pd.DataFrame:
    return pd.DataFrame({
        "listing_key": [f"k{i}" for i in range(9)],
        "product_name": [f"Laptop {i}" for i in range(9)],
        "price": [4000000, 4500000, 5000000, 12000000, 13000000, 14000000, 30000000, 35000000, 40000000],
        "rating": [4.0, 4.2, 4.1, 4.8, 4.7, 4.9, 5.0, 4.9, 5.0],
        "review_count_resolved": [5.0, 8.0, 6.0, 50.0, 60.0, 55.0, 12.0, 15.0, 20.0]
    })


def test_run_kmeans_clustering_adds_cluster_column(sample_clean_df: pd.DataFrame):
    features = ["price", "rating", "review_count_resolved"]
    clustered = run_kmeans_clustering(sample_clean_df, features, n_clusters=3, random_state=42)

    assert "cluster" in clustered.columns
    assert len(clustered) == len(sample_clean_df)
    assert set(clustered["cluster"].unique()) == {0, 1, 2}
    assert clustered["cluster"].isnull().sum() == 0


def test_report_and_export_creates_file(sample_clean_df: pd.DataFrame, tmp_path: Path):
    features = ["price", "rating", "review_count_resolved"]
    clustered = run_kmeans_clustering(sample_clean_df, features, n_clusters=3, random_state=42)

    output_csv = tmp_path / "output_test_clustered.csv"
    report_and_export(clustered, features, output_csv)

    assert output_csv.exists()
    loaded = pd.read_csv(output_csv)
    assert len(loaded) == len(sample_clean_df)
    assert "cluster" in loaded.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_k_mean_clustering.py -v`  
Expected: FAIL (cannot import `run_kmeans_clustering` / `report_and_export`)

- [ ] **Step 3: Implement clustering, reporting, export, and `main()` in `scripts/k_mean.py`**

Append to `scripts/k_mean.py`:
```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def run_kmeans_clustering(
    df: pd.DataFrame,
    features: list[str],
    n_clusters: int = 3,
    random_state: int = 42,
) -> pd.DataFrame:
    """Scale features and perform K-Means clustering, adding 'cluster' column to df."""
    df_clustered = df.copy()

    X = df_clustered[features].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init="auto",
    )
    df_clustered["cluster"] = kmeans.fit_predict(X_scaled)
    return df_clustered


def report_and_export(
    df: pd.DataFrame,
    features: list[str],
    output_path: str | Path,
) -> None:
    """Print cluster summary metrics and export clustered dataset to CSV."""
    print("\n" + "=" * 60)
    print("--- Ringkasan Karakteristik Segmen Cluster ---")
    print("=" * 60)

    total_rows = len(df)
    cluster_counts = df["cluster"].value_counts().sort_index()

    summary_rows = []
    for c_id in sorted(df["cluster"].unique()):
        sub = df[df["cluster"] == c_id]
        count = len(sub)
        pct = (count / total_rows) * 100
        mean_price = sub["price"].mean()
        median_price = sub["price"].median()
        mean_rating = sub["rating"].mean()
        mean_reviews = sub["review_count_resolved"].mean()

        print(f"\n[Cluster {c_id}] : {count:,} produk ({pct:.1f}%)")
        print(f"  - Rata-rata Harga  : Rp {mean_price:,.0f} (Median: Rp {median_price:,.0f})")
        print(f"  - Rata-rata Rating : {mean_rating:.2f} / 5.0")
        print(f"  - Rata-rata Ulasan : {mean_reviews:.1f} ulasan")

        summary_rows.append({
            "cluster": c_id,
            "count": count,
            "pct": round(pct, 2),
            "mean_price": round(mean_price, 2),
            "median_price": round(median_price, 2),
            "mean_rating": round(mean_rating, 2),
            "mean_reviews": round(mean_reviews, 2),
        })

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_file, index=False)
    print("\n" + "=" * 60)
    print(f"Data hasil clustering berhasil disimpan ke: {out_file.resolve()}")
    print("=" * 60)


def main() -> None:
    input_path = Path("kaggle/release/v1.0.3/cleaning_decisions.csv")
    output_path = Path("kaggle/release/v1.0.3/clustered_laptops.csv")
    features = [
        "price",
        "rating",
        "review_count_resolved",
    ]

    df_raw = load_and_audit_data(input_path, features)
    df_clean = clean_dataset(df_raw, features)
    df_clustered = run_kmeans_clustering(df_clean, features, n_clusters=3, random_state=42)
    report_and_export(df_clustered, features, output_path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_k_mean_clustering.py -v`  
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add scripts/k_mean.py tests/test_k_mean_clustering.py
git commit -m "feat: complete clustering, reporting, and export in k_mean.py with tests"
```

---

### Task 3: End-to-End Verification on Real Dataset

**Files:**
- Output generated: `kaggle/release/v1.0.3/clustered_laptops.csv`

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/test_k_mean_cleaning.py tests/test_k_mean_clustering.py -v`  
Expected: All tests PASS.

- [ ] **Step 2: Run `python scripts/k_mean.py` on the real dataset**

Run: `python scripts/k_mean.py`  
Expected:
- Audit table printed showing 71 rating nulls and 589 review_count nulls.
- 64 excluded accessories filtered.
- Complete cases: 1,588 rows remaining.
- 3 clusters generated and profiled.
- CSV saved to `kaggle/release/v1.0.3/clustered_laptops.csv`.

- [ ] **Step 3: Verify exported CSV file**

Run:
```bash
python -c "import pandas as pd; df = pd.read_csv('kaggle/release/v1.0.3/clustered_laptops.csv'); assert len(df) == 1588; assert df[['price', 'rating', 'review_count_resolved', 'cluster']].isnull().sum().sum() == 0; print('SUCCESS: Exported CSV contains', len(df), 'clean clustered rows.')"
```
Expected:
`SUCCESS: Exported CSV contains 1588 clean clustered rows.`
