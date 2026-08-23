"""Unit tests for production config and pipeline state persistence."""

from pathlib import Path

from laptop_market_scraper.pipeline.state import (
    PipelineStage,
    PipelineState,
    ProductionConfig,
    load_pipeline_state,
    load_production_config,
    save_pipeline_state,
)


def test_pipeline_stage_enum_values():
    assert PipelineStage.INITIALIZED == "INITIALIZED"
    assert PipelineStage.PREFLIGHT_COMPLETE == "PREFLIGHT_COMPLETE"
    assert PipelineStage.CRAWLING == "CRAWLING"
    assert PipelineStage.CRAWL_COMPLETE == "CRAWL_COMPLETE"
    assert PipelineStage.EXPORT_COMPLETE == "EXPORT_COMPLETE"
    assert PipelineStage.QUALITY_COMPLETE == "QUALITY_COMPLETE"
    assert PipelineStage.AUDIT_COMPLETE == "AUDIT_COMPLETE"
    assert PipelineStage.FAILED == "FAILED"


def test_production_config_defaults():
    config = ProductionConfig()
    assert config.target_unique_eligible == 5000
    assert config.minimum_research_sample == 3000
    assert config.concurrent_requests == 4
    assert config.require_clean_git is True
    assert config.required_acquisition_tag == "dataset-acquisition-v1.0"
    assert config.run_audit_after_crawl is True
    assert config.run_quality_after_crawl is True
    assert config.max_pages_total == 500


def test_load_production_config_default_file():
    config = load_production_config("config/production.yaml")
    assert config.target_unique_eligible == 5000
    assert config.minimum_research_sample == 3000
    assert config.concurrent_requests == 4
    assert config.require_clean_git is True
    assert config.required_acquisition_tag == "dataset-acquisition-v1.0"
    assert config.run_audit_after_crawl is True
    assert config.run_quality_after_crawl is True
    assert config.max_pages_total == 500


def test_load_production_config_custom_path(tmp_path: Path):
    custom_yaml = tmp_path / "custom_prod.yaml"
    custom_yaml.write_text(
        """
production:
  target_unique_eligible: 1000
  minimum_research_sample: 500
  concurrent_requests: 2
  require_clean_git: false
  required_acquisition_tag: "test-tag"
  run_audit_after_crawl: false
  run_quality_after_crawl: false
  max_pages_total: 50
""",
        encoding="utf-8",
    )

    config = load_production_config(custom_yaml)
    assert config.target_unique_eligible == 1000
    assert config.minimum_research_sample == 500
    assert config.concurrent_requests == 2
    assert config.require_clean_git is False
    assert config.required_acquisition_tag == "test-tag"
    assert config.run_audit_after_crawl is False
    assert config.run_quality_after_crawl is False
    assert config.max_pages_total == 50


def test_load_production_config_nonexistent_path(tmp_path: Path):
    nonexistent = tmp_path / "nonexistent.yaml"
    config = load_production_config(nonexistent)
    assert config.target_unique_eligible == 5000


def test_save_and_load_pipeline_state(tmp_path: Path):
    crawl_dir = tmp_path / "crawl_run_1"
    state = PipelineState(
        run_id="run-123",
        stage=PipelineStage.INITIALIZED,
        target_unique_eligible=5000,
        actual_unique_eligible=120,
    )

    saved_path = save_pipeline_state(state, crawl_dir)
    assert saved_path == crawl_dir / "pipeline_state.json"
    assert saved_path.exists()

    loaded = load_pipeline_state(crawl_dir)
    assert loaded is not None
    assert loaded.run_id == "run-123"
    assert loaded.stage == PipelineStage.INITIALIZED
    assert loaded.target_unique_eligible == 5000
    assert loaded.actual_unique_eligible == 120
    assert loaded.updated_at != ""


def test_load_pipeline_state_nonexistent(tmp_path: Path):
    crawl_dir = tmp_path / "empty_dir"
    loaded = load_pipeline_state(crawl_dir)
    assert loaded is None


def test_pipeline_stage_transitions(tmp_path: Path):
    crawl_dir = tmp_path / "crawl_run_transitions"
    state = PipelineState(run_id="run-trans", stage=PipelineStage.INITIALIZED)

    # INITIALIZED -> PREFLIGHT_COMPLETE -> CRAWLING -> CRAWL_COMPLETE
    save_pipeline_state(state, crawl_dir)
    assert load_pipeline_state(crawl_dir).stage == PipelineStage.INITIALIZED

    state.stage = PipelineStage.PREFLIGHT_COMPLETE
    save_pipeline_state(state, crawl_dir)
    assert load_pipeline_state(crawl_dir).stage == PipelineStage.PREFLIGHT_COMPLETE

    state.stage = PipelineStage.CRAWLING
    save_pipeline_state(state, crawl_dir)
    assert load_pipeline_state(crawl_dir).stage == PipelineStage.CRAWLING

    state.stage = PipelineStage.CRAWL_COMPLETE
    state.actual_unique_eligible = 5050
    save_pipeline_state(state, crawl_dir)

    final_state = load_pipeline_state(crawl_dir)
    assert final_state.stage == PipelineStage.CRAWL_COMPLETE
    assert final_state.actual_unique_eligible == 5050


def test_atomic_save_overwrites(tmp_path: Path):
    crawl_dir = tmp_path / "crawl_atomic"
    state = PipelineState(run_id="run-atomic", stage=PipelineStage.INITIALIZED)

    save_pipeline_state(state, crawl_dir)
    tmp_files = list(crawl_dir.glob("*.tmp"))
    assert len(tmp_files) == 0

    state.stage = PipelineStage.QUALITY_COMPLETE
    save_pipeline_state(state, crawl_dir)
    tmp_files = list(crawl_dir.glob("*.tmp"))
    assert len(tmp_files) == 0

    loaded = load_pipeline_state(crawl_dir)
    assert loaded.stage == PipelineStage.QUALITY_COMPLETE
