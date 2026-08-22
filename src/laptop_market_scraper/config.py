import yaml
from pathlib import Path
from pydantic_settings import BaseSettings

from laptop_market_scraper.models import SeedSource


class AppSettings(BaseSettings):
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


def load_seeds(config_path: str = "config/seeds.yaml") -> list[SeedSource]:
    path = Path(config_path)
    if not path.exists():
        return []
        
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    seeds_data = data.get("seeds", [])
    return [SeedSource(**seed) for seed in seeds_data]
