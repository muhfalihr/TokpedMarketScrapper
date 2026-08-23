from pathlib import Path
from typing import Any

import yaml

from laptop_market_scraper.ml_freeze.models import (
    FreezeEligibilityConfig,
    FreezeOutputsConfig,
    FreezeRepresentation,
    FreezeReviewCountConfig,
    MLFreezeConfig,
)

__all__ = [
    "FreezeEligibilityConfig",
    "FreezeOutputsConfig",
    "FreezeRepresentation",
    "FreezeReviewCountConfig",
    "MLFreezeConfig",
    "load_ml_freeze_config",
]


def load_ml_freeze_config(config_path: str | Path = "config/ml_freeze.yaml") -> MLFreezeConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"ML freeze configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    freeze_data = data.get("freeze", data)
    return MLFreezeConfig.model_validate(freeze_data)
