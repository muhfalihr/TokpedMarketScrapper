"""Tests for ProductionPipeline orchestrator and extended manifest generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tokped_market_scrapper.cli import app
from tokped_market_scrapper.manifest import generate_manifest, write_manifest
from tokped_market_scrapper.pipeline import (
    PipelineStage,
    PipelineState,
    ProductionPipeline,
)


def test_manifest_extension_with_pipeline_metadata(tmp_path: Path):
    seed_config = tmp_path / "seeds.yaml"
    seed_config.write_text("search:\n  rows: 60\nseeds:\n  - query: laptop\n", encoding="utf-8")

    prod_config = tmp_path / "production.yaml"
    prod_config.write_text("production:\n  target_unique_eligible: 5000\n", encoding="utf-8")

    pipeline_meta = {
        "target_unique_eligible": 5000,
        "actual_unique_eligible": 4982,
        "target_reached": True,
    }
    acquisition_meta = {
        "tag": "dataset-acquisition-v1.0",
        "commit": "ebdec1d12345",
        "contract_sha256": "sha256contract",
        "seed_config_sha256": "sha256seed",
        "production_config_sha256": "sha256prod",
    }
    feature_audit_meta = {
        "registry_version": "1.0",
        "artifact_sha256": "sha256audit",
    }

    manifest = generate_manifest(
        seed_config=seed_config,
        production_config=prod_config,
        pipeline_meta=pipeline_meta,
        acquisition_meta=acquisition_meta,
        feature_audit_meta=feature_audit_meta,
    )

    assert "pipeline" in manifest
    assert manifest["pipeline"]["target_unique_eligible"] == 5000
    assert manifest["pipeline"]["actual_unique_eligible"] == 4982
    assert manifest["pipeline"]["target_reached"] is True

    assert "acquisition" in manifest
    assert manifest["acquisition"]["tag"] == "dataset-acquisition-v1.0"
    assert manifest["acquisition"]["commit"] == "ebdec1d12345"
    assert manifest["acquisition"]["contract_sha256"] == "sha256contract"

    assert "feature_audit" in manifest
    assert manifest["feature_audit"]["registry_version"] == "1.0"
    assert manifest["feature_audit"]["artifact_sha256"] == "sha256audit"

    manifest_file = write_manifest(tmp_path, manifest)
    assert manifest_file.exists()


def test_production_pipeline_executes_all_stages(tmp_path: Path):
    crawl_dir = tmp_path / "crawl"
    prod_config = tmp_path / "production.yaml"
    seed_config = tmp_path / "seeds.yaml"

    prod_config.write_text(
        "production:\n  target_unique_eligible: 100\n  max_pages_total: 10\n",
        encoding="utf-8",
    )
    seed_config.write_text("search:\n  rows: 60\nseeds:\n  - query: laptop\n", encoding="utf-8")

    pipeline = ProductionPipeline(
        production_config_path=prod_config,
        seed_config_path=seed_config,
        crawl_dir=crawl_dir,
        run_id="test_run_001",
        resume=False,
        skip_audit=False,
    )

    with patch("tokped_market_scrapper.pipeline.production.TokopediaLaptopSpider") as mock_spider_cls:
        mock_spider = MagicMock()
        mock_spider_cls.return_value = mock_spider

        result_state = pipeline.run()

    assert result_state.stage == PipelineStage.AUDIT_COMPLETE
    assert (crawl_dir / "pipeline_state.json").exists()
    assert (crawl_dir / "manifest.json").exists()
    assert mock_spider.start.called


def test_production_pipeline_resumes_from_interrupted_stage(tmp_path: Path):
    crawl_dir = tmp_path / "crawl"
    crawl_dir.mkdir(parents=True, exist_ok=True)
    prod_config = tmp_path / "production.yaml"
    seed_config = tmp_path / "seeds.yaml"

    prod_config.write_text("production:\n  target_unique_eligible: 100\n", encoding="utf-8")
    seed_config.write_text("search:\n  rows: 60\nseeds:\n  - query: laptop\n", encoding="utf-8")

    # Simulate already completed crawl stage
    initial_state = PipelineState(
        run_id="test_resume_001",
        stage=PipelineStage.CRAWL_COMPLETE,
        target_unique_eligible=100,
        actual_unique_eligible=80,
    )
    (crawl_dir / "pipeline_state.json").write_text(
        initial_state.model_dump_json(indent=2), encoding="utf-8"
    )

    pipeline = ProductionPipeline(
        production_config_path=prod_config,
        seed_config_path=seed_config,
        crawl_dir=crawl_dir,
        run_id="test_resume_001",
        resume=True,
        skip_audit=True,
    )

    with patch("tokped_market_scrapper.pipeline.production.TokopediaLaptopSpider") as mock_spider_cls:
        result_state = pipeline.run()

        # Spider should NOT be started because crawl stage was already complete
        assert not mock_spider_cls.called

    assert result_state.stage == PipelineStage.QUALITY_COMPLETE
    assert (crawl_dir / "manifest.json").exists()


def test_production_run_cli(tmp_path: Path):
    runner = CliRunner()
    crawl_dir = tmp_path / "crawl_cli"
    prod_config = tmp_path / "production.yaml"
    seed_config = tmp_path / "seeds.yaml"

    prod_config.write_text("production:\n  target_unique_eligible: 50\n", encoding="utf-8")
    seed_config.write_text("search:\n  rows: 60\nseeds:\n  - query: laptop\n", encoding="utf-8")

    with patch("tokped_market_scrapper.pipeline.production.TokopediaLaptopSpider"):
        result = runner.invoke(
            app,
            [
                "production-run",
                "--production-config",
                str(prod_config),
                "--seed-config",
                str(seed_config),
                "--crawl-dir",
                str(crawl_dir),
                "--run-id",
                "cli_run_001",
                "--skip-audit",
            ],
        )

    assert result.exit_code == 0
    assert "Production pipeline run completed" in result.output or (crawl_dir / "manifest.json").exists()
