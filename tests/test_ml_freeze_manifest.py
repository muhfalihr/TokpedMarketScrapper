"""Tests for ML freeze manifest module (Task 10)."""

import pandas as pd
import pytest

from laptop_market_scraper.ml_freeze.config import load_ml_freeze_config
from laptop_market_scraper.ml_freeze.decisions import build_cleaning_decision
from laptop_market_scraper.ml_freeze.eligibility import EligibilityAssessment
from laptop_market_scraper.ml_freeze.manifest import build_ml_dataset_manifest
from laptop_market_scraper.ml_freeze.matrices import FrozenMatrices
from laptop_market_scraper.ml_freeze.models import (
    EligibilityDecision,
    EligibilityReason,
    ReviewCountSemanticStatus,
)
from laptop_market_scraper.ml_freeze.review_semantics import ReviewCountResolution

_CONFIG = load_ml_freeze_config("config/ml_freeze.yaml")


@pytest.fixture
def sample_manifest(tmp_path):
    r1 = pd.DataFrame([{"listing_key": "k1", "price": 10_000_000, "rating": 4.5}])
    r2 = pd.DataFrame(
        [{"listing_key": "k1", "price": 10_000_000, "rating": 4.5, "review_count": 10}]
    )
    matrices = FrozenMatrices(r1=r1, r2=r2)

    elig = EligibilityAssessment(
        listing_key="k1",
        decision=EligibilityDecision.VALID_LAPTOP,
        reason=EligibilityReason.VALID_LAPTOP,
    )
    res = ReviewCountResolution(
        listing_key="k1",
        original_value=10,
        resolved_value=10,
        semantic_status=ReviewCountSemanticStatus.OBSERVED_COUNT,
    )
    decision = build_cleaning_decision(
        row={"listing_key": "k1", "price": 10_000_000, "rating": 4.5},
        eligibility=elig,
        review_resolution=res,
    )

    r1_file = tmp_path / "r1.parquet"
    r1_file.write_bytes(b"dummy-parquet-1")
    r2_file = tmp_path / "r2.parquet"
    r2_file.write_bytes(b"dummy-parquet-2")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("freeze:\n  version: 1.0\n")

    return build_ml_dataset_manifest(
        run_id="run-123",
        config=_CONFIG,
        matrices=matrices,
        decisions=[decision],
        source_paths={"freeze_config": config_file},
        artifact_paths={"r1_parquet": r1_file, "r2_parquet": r2_file},
        git_commit="abcdef1234567890",
        acquisition_tag="dataset-acquisition-v1.0",
    )


def test_manifest_hashes_r1_and_r2(sample_manifest):
    assert len(sample_manifest["representations"]["R1"]["sha256"]) == 64
    assert len(sample_manifest["representations"]["R2"]["sha256"]) == 64


def test_manifest_locks_feature_contract(sample_manifest):
    assert sample_manifest["representations"]["R1"]["features"] == ["price", "rating"]
    assert sample_manifest["representations"]["R2"]["features"] == [
        "price",
        "rating",
        "review_count",
    ]


def test_manifest_records_provenance(sample_manifest):
    assert sample_manifest["artifact"] == "ml-dataset-v1.0.2"
    assert sample_manifest["source_run_id"] == "run-123"
    assert sample_manifest["git_commit"] == "abcdef1234567890"
    assert sample_manifest["acquisition_tag"] == "dataset-acquisition-v1.0"
