from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from laptop_market_scraper.models import SeedSource


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    log_level: str = "INFO"


def load_seeds(config_path: str = "config/seeds.yaml") -> list[SeedSource]:
    path = Path(config_path)
    if not path.exists():
        return []
        
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    seeds_data = data.get("seeds", [])
    return [SeedSource(**seed) for seed in seeds_data]
