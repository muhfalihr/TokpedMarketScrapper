import argparse
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

try:
    import joblib.externals.loky.backend.context as _loky_ctx

    _loky_ctx._count_physical_cores = lambda: (os.cpu_count() or 4, None)
except Exception:  # noqa: BLE001, S110 — monkeypatch bersifat opsional (fix loky Windows)
    pass

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# Fitur numerik default untuk clustering
FEATURES = ["price", "rating", "review_count", "sold"]
SKEWED_FEATURES = ["price", "review_count", "sold"]


def compute_bayesian_rating(
    df: pd.DataFrame,
    rating_col: str = "rating",
    review_col: str = "review_count",
    m: int = 10,
    c_prior: float | None = None,
) -> pd.Series:
    """Hitung Bayesian Weighted Rating (IMDb formula):

        WR = (v / (v + m)) * R + (m / (v + m)) * C

    Mencegah produk cold-start (1 ulasan bintang 5) disamaratakan dengan
    produk mapan bereputasi tinggi yang memiliki ratusan ulasan bintang 5.

    Args:
        df: DataFrame input
        rating_col: Kolom rating
        review_col: Kolom review count
        m: Bobot prior (ambang review minimum agar rating mendekati aslinya)
        c_prior: Rata-rata prior global. Jika None, diambil dari rata-rata produk dengan ulasan memadai.
    """
    v = df[review_col].fillna(0).astype(float)
    R = df[rating_col].fillna(0).astype(float)

    if c_prior is None:
        established = df[v >= m]
        c_prior = float(established[rating_col].mean()) if len(established) > 0 else float(R.mean())

    wr = (v / (v + m)) * R + (m / (v + m)) * c_prior
    return wr


def find_dataset(cli_path: str | Path | None = None) -> tuple[pd.DataFrame, str]:
    """Cari dataset hasil catalog-export; fallback ke dataset laptop lama."""
    if cli_path is not None:
        path = Path(cli_path)
        if path.exists():
            df = pd.read_csv(path)
            return df, str(path)
        print(f"Path tidak ditemukan: {path}")

    # 1) Export katalog terbaru (skema referensi: price, rating, review_count, sold, ...)
    candidates = sorted(Path("data/processed").glob("*/tokopedia_products_v2.csv"))
    if candidates:
        path = candidates[-1]
        df = pd.read_csv(path)
        if all(c in df.columns for c in FEATURES):
            return df, str(path)

    # 2) Fallback: dataset laptop lama (kolom review_count_resolved)
    legacy = Path("kaggle/release/v1.0.3/cleaning_decisions.csv")
    if legacy.exists():
        df = pd.read_csv(legacy)
        if "eligibility_decision" in df.columns:
            df = df[df["eligibility_decision"] == "VALID_LAPTOP"]
        df = df.rename(columns={"review_count_resolved": "review_count"})
        if "product_name" in df.columns:
            df = df.rename(columns={"product_name": "name"})
        return df, str(legacy)

    raise SystemExit(
        "Dataset tidak ditemukan. Jalankan dulu:\n"
        "  tokped-scraper catalog-collect\n"
        "  tokped-scraper catalog-enrich --run-id <id>\n"
        "  tokped-scraper catalog-export --run-id <id>\n"
        "atau berikan path CSV: python scripts/k_mean.py <path.csv>"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="K-Means clustering pada data produk Tokopedia dengan opsi penanganan rating skewness."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=None,
        help="Path ke file dataset CSV (opsional, default: file terbaru di data/processed/)",
    )
    parser.add_argument(
        "--min-reviews",
        type=int,
        default=0,
        help="Filter produk dengan review_count >= MIN_REVIEWS untuk mengeliminasi cold-start (default: 0)",
    )
    parser.add_argument(
        "--use-weighted-rating",
        action="store_true",
        help="Gunakan Bayesian Weighted Rating (IMDb formula) sebagai pengganti raw rating",
    )
    parser.add_argument(
        "--m-prior",
        type=int,
        default=10,
        help="Ambang bobot prior ulasan (m) untuk Bayesian Weighted Rating (default: 10)",
    )
    parser.add_argument(
        "--exclude-rating",
        action="store_true",
        help="Keluarkan fitur rating dari proses clustering (hanya gunakan price, sold, review_count)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df, source = find_dataset(args.csv_path)
    print(f"Dataset: {source} ({len(df)} baris)")

    # 1. Filter minimum reviews (opsional)
    if args.min_reviews > 0 and "review_count" in df.columns:
        n_before_filter = len(df)
        df = df[df["review_count"] >= args.min_reviews].reset_index(drop=True)
        print(
            f"Filter review_count >= {args.min_reviews}: {len(df)} baris tersisa "
            f"(disaring {n_before_filter - len(df)} baris cold-start)"
        )

    # 2. Pemilihan fitur & Bayesian Weighted Rating (opsional)
    active_features = list(FEATURES)
    if args.exclude_rating:
        active_features = [c for c in active_features if c != "rating"]
        print("Fitur rating dinonaktifkan dari clustering.")
    elif args.use_weighted_rating and "rating" in df.columns and "review_count" in df.columns:
        df["weighted_rating"] = compute_bayesian_rating(df, m=args.m_prior)
        active_features = ["weighted_rating" if c == "rating" else c for c in active_features]
        print(f"Menggunakan Bayesian Weighted Rating (m={args.m_prior}) sebagai fitur pengganti raw rating.")

    features = [c for c in active_features if c in df.columns]
    skewed = [c for c in SKEWED_FEATURES if c in df.columns]

    print("\nNull per fitur:")
    print(df[features].isnull().sum())

    n_before = len(df)
    # price dan rating/weighted_rating wajib ada; review_count/sold kosong berarti 0
    required = [c for c in ("price", "rating", "weighted_rating") if c in features]
    df = df.dropna(subset=required).reset_index(drop=True)
    zero_filled = [c for c in features if c not in required]
    for col in zero_filled:
        df[col] = df[col].fillna(0)
    print(
        f"\nBaris terpakai: {len(df)} (buang {n_before - len(df)} baris null {required}; "
        f"kolom {zero_filled} yang kosong diisi 0)"
    )

    if len(df) < 10:
        raise SystemExit("Data terlalu sedikit setelah pemfilteran untuk clustering.")

    X = df[features].copy()
    for col in skewed:
        X[col] = np.log1p(X[col])

    X_scaled = StandardScaler().fit_transform(X)

    # Pemilihan K terbaik via silhouette
    results = []
    max_k = min(9, len(df))
    for k in range(2, max_k):
        model = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = model.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels)
        results.append((k, sil, model.inertia_))
        print(f"K={k} | Silhouette={sil:.4f} | Inertia={model.inertia_:.2f}")

    best_k, best_sil, _ = max(results, key=lambda r: r[1])
    print(f"\nK terbaik: {best_k} (silhouette={best_sil:.4f})")

    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init="auto")
    df["cluster"] = kmeans.fit_predict(X_scaled)

    print("\nJumlah data per cluster:")
    print(df["cluster"].value_counts().sort_index())

    print("\nProfil cluster (mean):")
    print(df.groupby("cluster")[features].mean().round(2))
    print("\nProfil cluster (median):")
    print(df.groupby("cluster")[features].median().round(2))

    # Karakter kategoris ringkas (bila tersedia)
    for col in ("category", "is_official"):
        if col in df.columns:
            print(f"\nDistribusi {col} per cluster:")
            print(df.groupby("cluster")[col].value_counts(normalize=True).unstack(fill_value=0).round(2))

    out_dir = Path("data/clusters")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "clustered_products.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nHasil clustering disimpan ke: {out_csv}")

    # Visualisasi pasangan fitur utama (dalam ruang log-scaled)
    plot_cols = list(features)
    n = len(plot_cols)
    fig, axes = plt.subplots(n, n, figsize=(4 * n, 4 * n))
    axes = np.atleast_2d(axes)
    for i, yi in enumerate(plot_cols):
        for j, xj in enumerate(plot_cols):
            ax = axes[i][j]
            scatter = ax.scatter(
                X[xj] if j >= 0 else X[yi],
                X[yi],
                c=df["cluster"],
                cmap="tab10",
                s=8,
                alpha=0.6,
            )
            ax.set_xlabel(f"log1p({xj})" if xj in skewed else xj if i == n - 1 else "")
            ax.set_ylabel(f"log1p({yi})" if yi in skewed else yi if j == 0 else "")
    fig.suptitle(f"K-Means (K={best_k}) — {len(df)} produk")
    fig.colorbar(scatter, ax=axes, label="cluster", shrink=0.6)
    out_png = out_dir / "clusters.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Plot disimpan ke: {out_png}")


if __name__ == "__main__":
    main()
