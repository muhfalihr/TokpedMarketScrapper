"""Loader for catalog seed YAML configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from tokped_market_scrapper.catalog.models import CatalogSeedConfig


def load_catalog_seed_config(config_path: str | Path = "config/catalog_seeds.yaml") -> CatalogSeedConfig:
    """Load and validate a catalog seed configuration file.

    Expected format::

        search:
          rows: 60
          category_sc: null     # null => all categories (multi-category mode)
          sort_code: "23"
          max_pages_per_task: 2
        tiers: [2, 1]           # 2 = Official Store, 1 = Gold Merchant
        keywords:
          - iphone
          - kulkas

    Args:
        config_path: Path to the YAML seed config.

    Returns:
        CatalogSeedConfig domain object.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config contains no keywords.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Catalog seed config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    search_cfg = data.get("search") or {}

    keywords_raw = data.get("keywords") or []
    keywords = tuple(str(k).strip() for k in keywords_raw if str(k).strip())

    if not keywords:
        raise ValueError(f"Catalog seed config {path} defines no keywords")

    tiers_raw = data.get("tiers") or [2, 1]
    tiers = tuple(int(t) for t in tiers_raw)

    category_sc = search_cfg.get("category_sc", None)
    if isinstance(category_sc, str) and category_sc.strip() == "":
        category_sc = None

    return CatalogSeedConfig(
        rows=int(search_cfg.get("rows", 60)),
        category_sc=category_sc,
        sort_code=str(search_cfg.get("sort_code", "23")),
        max_pages_per_task=int(search_cfg.get("max_pages_per_task", 2)),
        tiers=tiers,
        keywords=keywords,
    )
