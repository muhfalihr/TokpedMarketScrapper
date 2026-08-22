import os
from laptop_market_scraper.config import AppSettings, load_seeds


def test_app_settings_loads_env_vars(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = AppSettings()
    assert settings.log_level == "DEBUG"


def test_load_seeds(tmp_path):
    seed_yaml = """
seeds:
  - source_type: search
    query: laptop
    url: "https://www.tokopedia.com/search?st=product&q=laptop"
"""
    config_file = tmp_path / "seeds.yaml"
    config_file.write_text(seed_yaml)
    
    seeds = load_seeds(str(config_file))
    
    assert len(seeds) == 1
    assert seeds[0].source_type == "search"
    assert seeds[0].query == "laptop"
    assert str(seeds[0].url) == "https://www.tokopedia.com/search?st=product&q=laptop"
