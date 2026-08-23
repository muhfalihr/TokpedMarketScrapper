from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from laptop_market_scraper.models import SearchSeed


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    log_level: str = "INFO"


def load_seeds(config_path: str | Path = "config/seeds.yaml") -> list[SearchSeed]:
    path = Path(config_path)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    search_cfg = data.get("search", {})
    default_max_pages = search_cfg.get("max_pages_per_seed", 20)

    seeds_data = data.get("seeds", [])
    results: list[SearchSeed] = []
    for item in seeds_data:
        if isinstance(item, dict):
            item_copy = item.copy()
            if "max_pages" not in item_copy:
                item_copy["max_pages"] = default_max_pages
            if "kind" not in item_copy:
                item_copy["kind"] = "generic"
            item_copy.pop("source_type", None)
            item_copy.pop("url", None)
            results.append(SearchSeed(**item_copy))
    return results


def load_search_config(config_path: str | Path = "config/seeds.yaml") -> dict[str, Any]:
    path = Path(config_path)
    default_config = {
        "rows": 60,
        "category_sc": "297",
        "sort_code": "23",
        "max_pages_per_seed": 20,
    }
    if not path.exists():
        return default_config

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    search_cfg = data.get("search", {})
    for k, v in search_cfg.items():
        default_config[k] = v
    return default_config

