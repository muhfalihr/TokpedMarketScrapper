import os
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    INITIALIZED = "INITIALIZED"
    PREFLIGHT_COMPLETE = "PREFLIGHT_COMPLETE"
    CRAWLING = "CRAWLING"
    CRAWL_COMPLETE = "CRAWL_COMPLETE"
    EXPORT_COMPLETE = "EXPORT_COMPLETE"
    QUALITY_COMPLETE = "QUALITY_COMPLETE"
    AUDIT_COMPLETE = "AUDIT_COMPLETE"
    FAILED = "FAILED"


class ProductionConfig(BaseModel):
    target_unique_eligible: int = 5000
    minimum_research_sample: int = 3000
    concurrent_requests: int = 4
    require_clean_git: bool = True
    required_acquisition_tag: str = "dataset-acquisition-v1.0"
    run_audit_after_crawl: bool = True
    run_quality_after_crawl: bool = True
    max_pages_total: int = 500


class PipelineState(BaseModel):
    run_id: str
    stage: PipelineStage = PipelineStage.INITIALIZED
    target_unique_eligible: int = 5000
    actual_unique_eligible: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def load_production_config(path: Path | str = "config/production.yaml") -> ProductionConfig:
    p = Path(path)
    if not p.exists():
        return ProductionConfig()

    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if isinstance(data, dict) and "production" in data and isinstance(data["production"], dict):
        prod_data = data["production"]
    elif isinstance(data, dict):
        prod_data = data
    else:
        prod_data = {}

    return ProductionConfig(**prod_data)


def save_pipeline_state(state: PipelineState, crawl_dir: Path) -> Path:
    crawl_dir = Path(crawl_dir)
    crawl_dir.mkdir(parents=True, exist_ok=True)

    target_path = crawl_dir / "pipeline_state.json"
    tmp_path = crawl_dir / "pipeline_state.json.tmp"

    state_json = state.model_dump_json(indent=2)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(state_json)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, target_path)
    return target_path


def load_pipeline_state(crawl_dir: Path) -> PipelineState | None:
    crawl_dir = Path(crawl_dir)
    target_path = crawl_dir / "pipeline_state.json"

    if not target_path.exists():
        return None

    content = target_path.read_text(encoding="utf-8")
    return PipelineState.model_validate_json(content)
