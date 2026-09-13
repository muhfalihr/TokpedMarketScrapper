import os
import warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

try:
    import joblib.externals.loky.backend.context as _loky_ctx
    _loky_ctx._count_physical_cores = lambda: (os.cpu_count() or 4, None)
except Exception:
    pass

from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


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
