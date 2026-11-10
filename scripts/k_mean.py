import os
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

try:
    import joblib.externals.loky.backend.context as _loky_ctx
    _loky_ctx._count_physical_cores = lambda: (os.cpu_count() or 4, None)
except Exception:  # noqa: BLE001, S110 — monkeypatch bersifat opsional (fix loky Windows)
    pass

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# Fitur numerik untuk clustering (sesuai dataset katalog multi-kategori).
# price/sold/review_count sangat skewed -> transformasi log1p sebelum scaling.
FEATURES = ["price", "rating", "review_count", "sold"]
SKEWED_FEATURES = ["price", "review_count", "sold"]


def find_dataset() -> tuple[pd.DataFrame, str]:
    """Cari dataset hasil catalog-export; fallback ke dataset laptop lama."""
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
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


def main() -> None:
    df, source = find_dataset()
    print(f"Dataset: {source} ({len(df)} baris)")

    features = [c for c in FEATURES if c in df.columns]
    skewed = [c for c in SKEWED_FEATURES if c in df.columns]

    print("\nNull per fitur:")
    print(df[features].isnull().sum())

    n_before = len(df)
    # price/rating wajib ada; review_count/sold kosong berarti 0 (belum ada review/penjualan)
    required = [c for c in ("price", "rating") if c in df.columns]
    df = df.dropna(subset=required).reset_index(drop=True)
    zero_filled = [c for c in features if c not in required]
    for col in zero_filled:
        df[col] = df[col].fillna(0)
    print(f"\nBaris terpakai: {len(df)} (buang {n_before - len(df)} baris null price/rating; "
          f"kolom {zero_filled} yang kosong diisi 0)")

    X = df[features].copy()
    for col in skewed:
        X[col] = np.log1p(X[col])

    X_scaled = StandardScaler().fit_transform(X)

    # Pemilihan K terbaik via silhouette
    results = []
    for k in range(2, 9):
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
    plot_cols = [c for c in ["price", "rating", "review_count", "sold"] if c in df.columns]
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
            ax.set_xlabel(f"log1p({xj})" if i == n - 1 else "")
            ax.set_ylabel(f"log1p({yi})" if j == 0 else "")
    fig.suptitle(f"K-Means (K={best_k}) — {len(df)} produk")
    fig.colorbar(scatter, ax=axes, label="cluster", shrink=0.6)
    out_png = out_dir / "clusters.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Plot disimpan ke: {out_png}")


if __name__ == "__main__":
    main()
