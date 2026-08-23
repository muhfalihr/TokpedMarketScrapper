from pathlib import Path
import pytest
from pydantic import ValidationError

from laptop_market_scraper.ml_readiness import (
    AssociationConfig,
    ExtremesConfig,
    MLReadinessConfig,
    RepresentationConfig,
    load_ml_readiness_config,
)


def test_load_valid_ml_readiness_config(tmp_path: Path):
    yaml_content = """
features:
  - price
  - rating
  - review_count

representations:
  R1:
    id: R1
    description: "Price + Rating"
    features:
      - price
      - rating
  R2:
    id: R2
    description: "Price + Rating + Review Count"
    features:
      - price
      - rating
      - review_count

extremes:
  price_lower_quantile: 0.01
  price_upper_quantile: 0.99
  iqr_multiplier: 1.5
  robust_z_threshold: 3.5
  sample_limit: 20

association:
  spearman_redundancy_threshold: 0.85
"""
    cfg_file = tmp_path / "ml_readiness.yaml"
    cfg_file.write_text(yaml_content, encoding="utf-8")

    config = load_ml_readiness_config(cfg_file)

    assert config.features == ["price", "rating", "review_count"]
    assert "R1" in config.representations
    assert config.representations["R1"].id == "R1"
    assert config.representations["R1"].features == ["price", "rating"]
    assert config.extremes.price_lower_quantile == 0.01
    assert config.extremes.price_upper_quantile == 0.99
    assert config.extremes.iqr_multiplier == 1.5
    assert config.extremes.robust_z_threshold == 3.5
    assert config.extremes.sample_limit == 20
    assert config.association.spearman_redundancy_threshold == 0.85


def test_load_actual_config_file():
    config = load_ml_readiness_config("config/ml_readiness.yaml")
    assert "price" in config.features
    assert "rating" in config.features
    assert "review_count" in config.features
    assert "R1" in config.representations
    assert "R2" in config.representations


def test_validation_missing_features():
    with pytest.raises(ValidationError):
        MLReadinessConfig(
            features=["price", "rating"],  # missing review_count
            representations={},
            extremes=ExtremesConfig(
                price_lower_quantile=0.01,
                price_upper_quantile=0.99,
                iqr_multiplier=1.5,
                robust_z_threshold=3.5,
                sample_limit=20,
            ),
            association=AssociationConfig(spearman_redundancy_threshold=0.85),
        )


def test_validation_invalid_quantile_range():
    # lower >= upper
    with pytest.raises(ValidationError):
        ExtremesConfig(
            price_lower_quantile=0.99,
            price_upper_quantile=0.01,
            iqr_multiplier=1.5,
            robust_z_threshold=3.5,
            sample_limit=20,
        )

    # out of (0, 1) bounds
    with pytest.raises(ValidationError):
        ExtremesConfig(
            price_lower_quantile=0.0,
            price_upper_quantile=0.99,
            iqr_multiplier=1.5,
            robust_z_threshold=3.5,
            sample_limit=20,
        )


def test_validation_invalid_extremes_thresholds():
    with pytest.raises(ValidationError):
        ExtremesConfig(
            price_lower_quantile=0.01,
            price_upper_quantile=0.99,
            iqr_multiplier=0.0,  # must be > 0
            robust_z_threshold=3.5,
            sample_limit=20,
        )

    with pytest.raises(ValidationError):
        ExtremesConfig(
            price_lower_quantile=0.01,
            price_upper_quantile=0.99,
            iqr_multiplier=1.5,
            robust_z_threshold=-1.0,  # must be > 0
            sample_limit=20,
        )


def test_validation_invalid_association():
    with pytest.raises(ValidationError):
        AssociationConfig(spearman_redundancy_threshold=1.5)  # must be <= 1.0

    with pytest.raises(ValidationError):
        AssociationConfig(spearman_redundancy_threshold=-0.1)  # must be >= 0.0


def test_load_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        load_ml_readiness_config("nonexistent_path/ml_readiness.yaml")
