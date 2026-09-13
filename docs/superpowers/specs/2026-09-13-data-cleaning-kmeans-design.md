# Technical Design: CSV Data Cleaning Pipeline for `scripts/k_mean.py`

**Date:** 2026-09-13  
**Status:** Approved  
**Target Script:** `scripts/k_mean.py`  
**Dataset:** `kaggle/release/v1.0.3/cleaning_decisions.csv`  

---

## 1. Problem Statement & Motivation

The existing script `scripts/k_mean.py` fails when executed due to:
1. `rows_miss = X[X.isnull().any()]` raising a pandas `IndexingError` because `any()` defaults to `axis=0` (returning column booleans instead of row indexers).
2. `X.dropna()` called without reassigning `X` or updating in-place.
3. If `X` were dropped separately without filtering the parent `DataFrame`, assigning `df["cluster"] = kmeans.fit_predict(X_scaled)` would result in an index length mismatch error.
4. Redundant features (`review_count_original` and `review_count_resolved`) are both present.
5. Ineligible rows (non-laptop components/accessories marked `EXCLUDE`) are not filtered prior to model training.

This design establishes a clean, robust, and modular data cleaning pipeline prior to scaling and K-Means clustering.

---

## 2. Goals & Non-Goals

### Goals
- Implement a structured, modular pipeline for loading, auditing, cleaning, scaling, and clustering the laptop dataset.
- Filter out non-laptop items (`eligibility_decision == 'VALID_LAPTOP'`).
- Audit missing values and cleanly drop incomplete records across chosen clustering features (Complete Cases strategy).
- Ensure strict index alignment between the cleaned DataFrame and the cluster assignments.
- Output informative console reports summarizing cleaning statistics (rows before vs after, null distributions) and cluster profiles (mean price, rating, review count).
- Export the resulting clustered DataFrame to a new CSV file (`kaggle/release/v1.0.3/clustered_laptops.csv`).

### Non-Goals
- Artificial imputation of missing reviews or ratings (user explicitly selected Complete Cases / dropna).
- Advanced automated hyperparameter tuning for $k$ (user specified $k=3$ with seed 42).
- Adding heavy GUI or web dashboard dependencies.

---

## 3. Data Specification & Selected Features

- **Source File:** `kaggle/release/v1.0.3/cleaning_decisions.csv` (2,227 total rows)
- **Target Output:** `kaggle/release/v1.0.3/clustered_laptops.csv`
- **Selected Clustering Features:**
  - `price` (numerical, list price in IDR)
  - `rating` (numerical, score 0.0 - 5.0)
  - `review_count_resolved` (numerical, resolved review count)

---

## 4. Pipeline Architecture & Component Design

The script `scripts/k_mean.py` is decomposed into isolated, testable functional components:

```
+---------------------------+
| 1. load_and_audit_data    | Reads CSV, calculates missing counts, displays null audit
+-------------+-------------+
              |
              v
+-------------+-------------+
| 2. clean_dataset          | Filters VALID_LAPTOP, executes dropna(subset=features)
+-------------+-------------+
              |
              v
+-------------+-------------+
| 3. run_kmeans_clustering  | StandardScaler -> KMeans(k=3, seed=42) -> assigns 'cluster'
+-------------+-------------+
              |
              v
+-------------+-------------+
| 4. report_and_export      | Prints cluster stats, saves to clustered_laptops.csv
+---------------------------+
```

### Component 1: `load_and_audit_data(csv_path: str | Path) -> pd.DataFrame`
- Checks file existence with informative error messages.
- Loads DataFrame from `csv_path`.
- Audits and prints missing values per column.
- Identifies rows with missing values using `df[features].isnull().any(axis=1)` (fixing the previous `IndexingError`).

### Component 2: `clean_dataset(df: pd.DataFrame, features: list[str]) -> pd.DataFrame`
- Filters for `eligibility_decision == "VALID_LAPTOP"` (removes 64 accessories/components).
- Drops rows containing nulls in `features`: `df_clean = df_valid.dropna(subset=features).copy()`.
- Resets or maintains consistent DataFrame indexing.
- Prints clear audit log:
  - Initial rows count.
  - Excluded non-laptop rows count.
  - Rows dropped due to missing feature values.
  - Final clean rows count (~1,588 rows).

### Component 3: `run_kmeans_clustering(df: pd.DataFrame, features: list[str], n_clusters: int = 3, random_state: int = 42) -> pd.DataFrame`
- Extracts matrix `X = df[features].values`.
- Applies `StandardScaler().fit_transform(X)`.
- Instantiates and fits `KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")`.
- Assigns predictions to `df["cluster"]`.

### Component 4: `report_and_export(df: pd.DataFrame, features: list[str], output_path: str | Path) -> None`
- Computes cluster summary statistics:
  - Product count and percentage per cluster.
  - Average price (formatted in IDR), median price, average rating, average review count.
- Exports cleaned and clustered DataFrame to `output_path`.
- Confirms successful export with path and row count.

---

## 5. Error Handling & Edge Cases

1. **File Not Found**: Raises `FileNotFoundError` if the CSV path does not exist.
2. **Missing Expected Columns**: Validates that `features` and `eligibility_decision` exist in DataFrame columns; raises `KeyError` with missing column names.
3. **Empty Dataset After Cleaning**: If `df_clean` has 0 rows, raises `ValueError("No valid rows remaining after data cleaning.")`.
4. **Index Consistency**: Guaranteed by operating directly on copies of the DataFrame rather than separate disconnected series, preventing shape mismatch.

---

## 6. Verification Plan

1. **Syntax & Unit Execution**:
   Run `python scripts/k_mean.py` from repository root.
2. **Success Criteria**:
   - Exit code 0 without any warnings or tracebacks.
   - Initial audit displays missing count breakdown.
   - Final row count matches expected complete cases (~1,588).
   - All 3 clusters (0, 1, 2) populated.
   - File `kaggle/release/v1.0.3/clustered_laptops.csv` is created and readable.
