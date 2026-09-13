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
