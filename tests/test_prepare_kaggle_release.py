"""Tests for prepare_kaggle_release script."""

import json
from pathlib import Path

import pandas as pd

from scripts.prepare_kaggle_release import (
    prepare_kaggle_release,
    render_kaggle_metadata,
    render_kaggle_readme,
)


def test_render_kaggle_metadata():
    meta = render_kaggle_metadata(
        dataset_id="user/dataset-name",
        title="Test Title",
        subtitle="Valid subtitle string with sufficient length",
        license_name="CC-BY-SA-4.0",
    )
    assert meta["id"] == "user/dataset-name"
    assert meta["title"] == "Test Title"
    assert meta["licenses"][0]["name"] == "CC-BY-SA-4.0"


def test_render_kaggle_metadata_validates_subtitle_length():
    import pytest

    with pytest.raises(ValueError, match="Kaggle subtitle length must be between 20 and 80"):
        render_kaggle_metadata(
            dataset_id="user/dataset-name",
            title="Test Title",
            subtitle="Too short",
        )


def test_render_kaggle_readme():
    manifest = {
        "artifact": "ml-dataset-v1.0.3",
        "source_run_id": "run-123",
        "source_rows": 2227,
        "cleaning": {"excluded_count": 64},
        "representations": {
            "R1": {"rows": 2106, "sha256": "abc"},
            "R2": {"rows": 1588, "sha256": "def"},
        },
    }
    readme = render_kaggle_readme(manifest)
    assert "# Tokopedia Laptop Market Dataset (2026)" in readme
    assert "ml-dataset-v1.0.3" in readme
    assert "2,106" in readme or "2106" in readme


def test_prepare_kaggle_release_creates_all_files(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    manifest = {
        "artifact": "ml-dataset-v1.0.3",
        "source_run_id": "run-123",
        "source_rows": 10,
        "representations": {
            "R1": {"rows": 8, "sha256": "sha1"},
            "R2": {"rows": 6, "sha256": "sha2"},
        },
    }
    (source_dir / "ml_dataset_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    df_r1 = pd.DataFrame([{"listing_key": "k1", "price": 1000, "rating": 4.5}])
    df_r1.to_parquet(source_dir / "r1_price_rating.parquet")

    df_r2 = pd.DataFrame([{"listing_key": "k1", "price": 1000, "rating": 4.5, "review_count": 5}])
    df_r2.to_parquet(source_dir / "r2_price_rating_review_count.parquet")

    output_dir = tmp_path / "target"
    prepare_kaggle_release(source_dir=source_dir, output_dir=output_dir)

    assert (output_dir / "r1_price_rating.parquet").exists()
    assert (output_dir / "r1_price_rating.csv").exists()
    assert (output_dir / "r2_price_rating_review_count.parquet").exists()
    assert (output_dir / "r2_price_rating_review_count.csv").exists()
    assert (output_dir / "dataset-metadata.json").exists()
    assert (output_dir / "README.md").exists()
