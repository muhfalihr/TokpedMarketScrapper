"""Verifikasi cepat: logika DBSCAN notebook Colab pada data katalog lokal.

Port headless dari bagian inti notebook DBSCAN (Bagian 3, 5, 6, 7, 8):
skenario prapemrosesan P0-P4, eps via titik lutut k-distance (kneed),
min_samples = 2 x dimensi, evaluasi indeks internal, dan stabilitas ARI.

Mendukung filter ambang review_count dan Bayesian Weighted Rating untuk
mengatasi rating skewness ekstrem.

Pemakaian:
    python scripts/dbscan_check.py [path.csv] [--min-reviews N] [--use-weighted-rating]
"""

import argparse
import warnings
from itertools import combinations
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from kneed import KneeLocator
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.cluster import DBSCAN
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

SEED = 42  # sama dengan notebook; jangan diubah
DEFAULT_FITUR = ["price", "sold", "rating", "review_count"]
DEFAULT_FITUR_LOG = ["price", "sold", "review_count"]


def compute_bayesian_rating(
    df: pd.DataFrame,
    rating_col: str = "rating",
    review_col: str = "review_count",
    m: int = 10,
    c_prior: float | None = None,
) -> pd.Series:
    """Hitung Bayesian Weighted Rating (IMDb formula):

        WR = (v / (v + m)) * R + (m / (v + m)) * C
    """
    v = df[review_col].fillna(0).astype(float)
    R = df[rating_col].fillna(0).astype(float)

    if c_prior is None:
        established = df[v >= m]
        c_prior = float(established[rating_col].mean()) if len(established) > 0 else float(R.mean())

    return (v / (v + m)) * R + (m / (v + m)) * c_prior


class Winsorizer(BaseEstimator, TransformerMixin):
    """Memotong nilai tiap kolom pada persentil bawah dan atas dari data fit."""

    def __init__(self, bawah=0.01, atas=0.99):
        self.bawah = bawah
        self.atas = atas

    def fit(self, X, y=None):
        self.batas_ = np.quantile(X, [self.bawah, self.atas], axis=0)
        return self

    def transform(self, X):
        return np.clip(X, self.batas_[0], self.batas_[1])


def kurva_jarak_k(Z, min_samples):
    jarak = NearestNeighbors(n_neighbors=min_samples).fit(Z).kneighbors(Z)[0][:, -1]
    return np.sort(jarak)


def eps_lutut(Z, min_samples):
    d = kurva_jarak_k(Z, min_samples)
    lutut = KneeLocator(np.arange(len(d)), d, curve="convex", direction="increasing")
    if lutut.knee is None:
        raise ValueError("Titik lutut tidak ditemukan; periksa kurva k-distance.")
    return float(d[lutut.knee])


def evaluasi(Z, label):
    """Indeks internal tanpa titik derau (label -1)."""
    bukan_derau = label != -1
    k = len(set(label[bukan_derau]))
    ukuran = pd.Series(label[bukan_derau]).value_counts() / len(label)
    hasil = {
        "Klaster": k,
        "Derau": float((~bukan_derau).mean()),
        "Klaster terbesar": float(ukuran.iloc[0]) if k else np.nan,
        "Klaster terkecil": float(ukuran.iloc[-1]) if k else np.nan,
    }
    if k >= 2:
        hasil.update(
            {
                "Silhouette": silhouette_score(Z[bukan_derau], label[bukan_derau]),
                "DBI": davies_bouldin_score(Z[bukan_derau], label[bukan_derau]),
                "CHI": calinski_harabasz_score(Z[bukan_derau], label[bukan_derau]),
            }
        )
    return hasil


def stabilitas_ari(pipe, X, indeks_sub):
    label_sub = [pd.Series(clone(pipe).fit_predict(X.iloc[idx]), index=idx) for idx in indeks_sub]
    ari = []
    for a, b in combinations(range(len(label_sub)), 2):
        irisan = label_sub[a].index.intersection(label_sub[b].index)
        ari.append(adjusted_rand_score(label_sub[a][irisan], label_sub[b][irisan]))
    return float(np.mean(ari)), float(np.std(ari))


def find_dataset(cli_path: str | Path | None = None) -> Path:
    if cli_path is not None:
        path = Path(cli_path)
        if path.exists():
            return path
        raise SystemExit(f"Path tidak ditemukan: {path}")
    candidates = sorted(Path("data/processed").glob("*/tokopedia_products_v2.csv"))
    if not candidates:
        raise SystemExit(
            "Belum ada export. Jalankan:\n"
            "  tokped-scraper catalog-collect\n"
            "  tokped-scraper catalog-enrich --run-id <id>\n"
            "  tokped-scraper catalog-export --run-id <id> --require-enrichment"
        )
    return candidates[-1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DBSCAN evaluation untuk dataset katalog Tokopedia."
    )
    parser.add_argument("csv_path", nargs="?", default=None, help="Path ke file dataset CSV (opsional)")
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
        help="Keluarkan fitur rating dari evaluasi (hanya gunakan price, sold, review_count)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    np.random.seed(SEED)
    csv_path = find_dataset(args.csv_path)
    df = pd.read_csv(csv_path)

    # Tentukan fitur aktif
    fitur = list(DEFAULT_FITUR)
    if args.exclude_rating:
        fitur = [c for c in fitur if c != "rating"]
        print("Fitur rating dinonaktifkan.")
    elif args.use_weighted_rating and "rating" in df.columns and "review_count" in df.columns:
        df["weighted_rating"] = compute_bayesian_rating(df, m=args.m_prior)
        fitur = ["weighted_rating" if c == "rating" else c for c in fitur]
        print(f"Menggunakan Bayesian Weighted Rating (m={args.m_prior}) menggantikan raw rating.")

    fitur_log = [c for c in DEFAULT_FITUR_LOG if c in fitur]

    # Filter review jika ditentukan
    if args.min_reviews > 0 and "review_count" in df.columns:
        n_before = len(df)
        df = df[df["review_count"] >= args.min_reviews].reset_index(drop=True)
        print(f"Filter review_count >= {args.min_reviews}: {len(df)} baris tersisa (disaring {n_before - len(df)} baris)")

    # --- Kontrak data notebook ---
    print(f"Data: {csv_path} — {df.shape[0]} baris, {df.shape[1]} kolom")
    hilang_kritis = df[fitur].isna().sum()
    print("Nilai hilang per fitur:")
    print(hilang_kritis.to_string())

    if df["product_id"].duplicated().any():
        raise SystemExit("GAGAL: product_id tidak unik (notebook mem-assert keunikan).")
    if hilang_kritis[["price", "sold"]].sum() > 0:
        print("PERINGATAN: price/sold masih ada NaN — jalankan enrich + --require-enrichment.")
    if "review_count" in hilang_kritis and hilang_kritis["review_count"] > 0:
        print(
            f"PERINGATAN: {hilang_kritis['review_count']} baris tanpa review_count "
            "(belum ter-enrich). StandardScaler notebook akan error jika tidak difilter. "
            "Disarankan: catalog-export --require-enrichment."
        )

    data = df.dropna(subset=fitur).reset_index(drop=True)
    print(f"Data bersih (dropna fitur): {data.shape[0]} baris")
    if "rating" in data.columns:
        print(f"Proporsi rating tepat 5,0: {data['rating'].eq(5).mean():.3f}")
    if "weighted_rating" in data.columns:
        print(f"Mean weighted_rating: {data['weighted_rating'].mean():.3f}, std: {data['weighted_rating'].std():.3f}")
    print(f"Skewness: {data[fitur].skew().round(2).to_dict()}")

    # --- Skenario prapemrosesan (identik notebook) ---
    X = data[fitur].astype(float)
    log_transform = ColumnTransformer(
        [("log", FunctionTransformer(np.log1p), fitur_log)],
        remainder="passthrough",
    )
    skenario = {
        "P0": Pipeline([("identitas", FunctionTransformer())]),
        "P1": Pipeline([("scaler", StandardScaler())]),
        "P2": Pipeline([("log", log_transform), ("scaler", StandardScaler())]),
        "P3": Pipeline(
            [("log", log_transform), ("winsor", Winsorizer()), ("scaler", StandardScaler())]
        ),
        "P4": Pipeline(
            [
                ("log", log_transform),
                ("winsor", Winsorizer()),
                ("scaler", StandardScaler()),
                ("pca", PCA(n_components=0.90, svd_solver="full", random_state=SEED)),
            ]
        ),
    }

    rng = np.random.default_rng(SEED)
    indeks_sub = [np.sort(rng.choice(len(X), int(0.8 * len(X)), replace=False)) for _ in range(30)]

    # --- eps via titik lutut + DBSCAN per skenario ---
    baris = []
    for nama, prep in skenario.items():
        Z = clone(prep).fit_transform(X)
        min_samples = 2 * Z.shape[1]
        eps = eps_lutut(Z, min_samples)
        pipe = Pipeline(
            [("prep", prep), ("model", DBSCAN(eps=eps, min_samples=min_samples))]
        )
        label = pipe.fit_predict(X)
        ari_mean, ari_sd = stabilitas_ari(pipe, X, indeks_sub)
        baris.append(
            {
                "Skenario": nama,
                "eps": round(eps, 3),
                "min_samples": min_samples,
                **evaluasi(Z, label),
                "ARI stabilitas": round(ari_mean, 3),
                "ARI sd": round(ari_sd, 3),
            }
        )

    hasil = pd.DataFrame(baris)
    print("\n=== Hasil DBSCAN per skenario ===")
    print(hasil.to_string(index=False))

    out = Path("data/clusters/hasil_dbscan_check.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    hasil.to_csv(out, index=False)
    print(f"\nTersimpan: {out}")


if __name__ == "__main__":
    main()
