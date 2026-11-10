from laptop_market_scraper.config import AppSettings, load_search_config, load_seeds


def test_app_settings_loads_env_vars(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = AppSettings()
    assert settings.log_level == "DEBUG"


def test_load_seeds(tmp_path):
    seed_yaml = """
search:
  rows: 60
  category_sc: "297"
  sort_code: "23"
  max_pages_per_seed: 15

seeds:
  - query: laptop
    kind: generic
  - query: laptop asus
    kind: brand
    brand_hint: ASUS
"""
    config_file = tmp_path / "seeds.yaml"
    config_file.write_text(seed_yaml)

    seeds = load_seeds(str(config_file))

    assert len(seeds) == 2
    assert seeds[0].query == "laptop"
    assert seeds[0].kind == "generic"
    assert seeds[0].max_pages == 15
    assert seeds[1].query == "laptop asus"
    assert seeds[1].kind == "brand"
    assert seeds[1].brand_hint == "ASUS"


def test_load_search_config(tmp_path):
    seed_yaml = """
search:
  rows: 50
  category_sc: "297"
  sort_code: "23"
  max_pages_per_seed: 10
"""
    config_file = tmp_path / "seeds.yaml"
    config_file.write_text(seed_yaml)

    cfg = load_search_config(str(config_file))
    assert cfg["rows"] == 50
    assert cfg["category_sc"] == "297"
    assert cfg["sort_code"] == "23"
    assert cfg["max_pages_per_seed"] == 10

