"""Production pipeline orchestrator for Tokopedia Laptop Scraper."""

import random
import string
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from laptop_market_scraper.audit import audit_features, export_feature_audit
from laptop_market_scraper.manifest import (
    generate_manifest,
    get_contract_sha256,
    get_file_sha256,
    write_manifest,
)
from laptop_market_scraper.pipeline.preflight import run_production_preflight
from laptop_market_scraper.pipeline.state import (
    PipelineStage,
    PipelineState,
    load_pipeline_state,
    load_production_config,
    save_pipeline_state,
)
from laptop_market_scraper.quality import export_quality_report, generate_quality_report
from laptop_market_scraper.spiders.tokopedia_laptop import TokopediaLaptopSpider
from laptop_market_scraper.storage import SQLiteStore


def _generate_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{timestamp}-{random_str}"


class ProductionPipeline(BaseModel):
    """Production pipeline orchestrator."""

    production_config_path: Path = Field(default_factory=lambda: Path("config/production.yaml"))
    seed_config_path: Path = Field(default_factory=lambda: Path("config/seeds.yaml"))
    crawl_dir: Path = Field(default_factory=lambda: Path("crawl_state/production"))
    run_id: str | None = None
    resume: bool = True
    skip_audit: bool = False

    def run(self) -> PipelineState:
        """Run the production pipeline stage by stage."""
        prod_cfg = load_production_config(self.production_config_path)

        # 1. Resolve run_id and state
        state: PipelineState | None = None
        if self.resume:
            state = load_pipeline_state(self.crawl_dir)

        if state is not None:
            run_id = state.run_id
        else:
            run_id = self.run_id if self.run_id else _generate_run_id()
            state = PipelineState(
                run_id=run_id,
                target_unique_eligible=prod_cfg.target_unique_eligible,
                stage=PipelineStage.INITIALIZED,
            )
            save_pipeline_state(state, self.crawl_dir)

        started_at = datetime.now(UTC).isoformat()

        # 2. Stage 1: Preflight
        if state.stage == PipelineStage.INITIALIZED:
            preflight_report = run_production_preflight(
                target_unique=prod_cfg.target_unique_eligible,
                configured_max_pages=prod_cfg.max_pages_total,
            )
            if not preflight_report.capacity_sufficient and preflight_report.warning:
                import logging
                logging.warning("Preflight Capacity Warning: %s", preflight_report.warning)

            state.stage = PipelineStage.PREFLIGHT_COMPLETE
            state.updated_at = datetime.now(UTC).isoformat()
            save_pipeline_state(state, self.crawl_dir)

        # Ensure directory structure and database
        self.crawl_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.crawl_dir / "laptops.db"
        store = SQLiteStore(db_path, data_dir=self.crawl_dir)

        # 3. Stage 2: Crawl
        if state.stage in (
            PipelineStage.INITIALIZED,
            PipelineStage.PREFLIGHT_COMPLETE,
            PipelineStage.CRAWLING,
        ):
            state.stage = PipelineStage.CRAWLING
            state.updated_at = datetime.now(UTC).isoformat()
            save_pipeline_state(state, self.crawl_dir)

            spider = TokopediaLaptopSpider(
                crawl_run_id=run_id,
                store=store,
                seed_config=str(self.seed_config_path),
                max_pages=prod_cfg.max_pages_total,
                max_items=prod_cfg.target_unique_eligible,
            )
            spider.start()

            actual_eligible = store.count_products(run_id=run_id)
            state.actual_unique_eligible = actual_eligible
            state.stage = PipelineStage.CRAWL_COMPLETE
            state.updated_at = datetime.now(UTC).isoformat()
            save_pipeline_state(state, self.crawl_dir)

        # 4. Stage 3: Export
        if state.stage == PipelineStage.CRAWL_COMPLETE:
            export_dir = self.crawl_dir / "exports" / run_id
            csv_path = export_dir / "laptops.csv"
            parquet_path = export_dir / "laptops.parquet"
            store.export_processed(csv_path, parquet_path)

            state.stage = PipelineStage.EXPORT_COMPLETE
            state.updated_at = datetime.now(UTC).isoformat()
            save_pipeline_state(state, self.crawl_dir)

        # 5. Stage 4: Quality Report
        if state.stage == PipelineStage.EXPORT_COMPLETE:
            reports_dir = self.crawl_dir / "reports" / run_id
            reports_dir.mkdir(parents=True, exist_ok=True)

            report_data = generate_quality_report(store=store, run_id=run_id)
            export_quality_report(reports_dir, report_data)

            state.stage = PipelineStage.QUALITY_COMPLETE
            state.updated_at = datetime.now(UTC).isoformat()
            save_pipeline_state(state, self.crawl_dir)

        # 6. Stage 5: Feature Audit
        artifact_sha256 = "none"
        reports_dir = self.crawl_dir / "reports" / run_id
        if not self.skip_audit and prod_cfg.run_audit_after_crawl:
            if state.stage == PipelineStage.QUALITY_COMPLETE:
                reports_dir.mkdir(parents=True, exist_ok=True)

                raw_candidates = [
                    self.crawl_dir / run_id,
                    self.crawl_dir / "raw" / run_id,
                    Path("data/raw") / run_id,
                    self.crawl_dir,
                ]
                raw_dir = next((p for p in raw_candidates if (p / "products.jsonl").exists()), None)

                audit_report = audit_features(
                    run_id=run_id,
                    store=store,
                    raw_dir=raw_dir,
                )
                json_path, _ = export_feature_audit(audit_report, reports_dir)
                artifact_sha256 = get_file_sha256(json_path)

                state.stage = PipelineStage.AUDIT_COMPLETE
                state.updated_at = datetime.now(UTC).isoformat()
                save_pipeline_state(state, self.crawl_dir)
            elif state.stage == PipelineStage.AUDIT_COMPLETE:
                json_path = reports_dir / "feature_audit.json"
                if json_path.exists():
                    artifact_sha256 = get_file_sha256(json_path)

        # 7. Stage 6: Manifest Generation & Export
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
        except (subprocess.SubprocessError, OSError):
            git_commit = "unknown"

        pipeline_meta = {
            "target_unique_eligible": state.target_unique_eligible,
            "actual_unique_eligible": state.actual_unique_eligible,
            "target_reached": state.actual_unique_eligible >= state.target_unique_eligible,
        }

        acquisition_meta = {
            "tag": prod_cfg.required_acquisition_tag,
            "commit": git_commit,
            "contract_sha256": get_contract_sha256(),
            "seed_config_sha256": get_file_sha256(self.seed_config_path),
            "production_config_sha256": get_file_sha256(self.production_config_path),
        }

        feature_audit_meta = {
            "registry_version": "1.0",
            "artifact_sha256": artifact_sha256,
        }

        manifest_data = generate_manifest(
            seed_config=self.seed_config_path,
            production_config=self.production_config_path,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            crawl_run_id=run_id,
            pipeline_meta=pipeline_meta,
            acquisition_meta=acquisition_meta,
            feature_audit_meta=feature_audit_meta if not self.skip_audit else None,
        )

        write_manifest(self.crawl_dir, manifest_data)
        reports_dir = self.crawl_dir / "reports" / run_id
        if reports_dir.exists():
            write_manifest(reports_dir, manifest_data)

        return state
