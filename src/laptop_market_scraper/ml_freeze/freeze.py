"""Freeze orchestrator — end-to-end ML dataset freeze pipeline."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from laptop_market_scraper.ml_freeze.config import load_ml_freeze_config
from laptop_market_scraper.ml_freeze.decisions import build_cleaning_decision
from laptop_market_scraper.ml_freeze.eligibility import assess_ml_eligibility
from laptop_market_scraper.ml_freeze.loader import load_ml_freeze_input
from laptop_market_scraper.ml_freeze.manifest import (
    build_ml_dataset_manifest,
    write_manifest,
)
from laptop_market_scraper.ml_freeze.matrices import build_ml_matrices
from laptop_market_scraper.ml_freeze.render import write_cleaning_artifacts
from laptop_market_scraper.ml_freeze.review_semantics import resolve_review_count
from laptop_market_scraper.ml_freeze.validate import validate_frozen_matrices
from laptop_market_scraper.storage import SQLiteStore


@dataclass(frozen=True)
class FreezeResult:
    source_row_count: int
    r1_rows: int
    r2_rows: int
    r1_path: Path
    r2_path: Path
    cleaning_decisions_path: Path
    excluded_observations_path: Path
    ambiguous_observations_path: Path
    manifest_path: Path
    readme_path: Path


def _get_git_commit() -> str:
    """Get current git commit hash, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _write_readme(output_dir: Path, manifest: dict) -> Path:
    """Write a human-readable README for the frozen dataset."""
    readme_path = output_dir / "README.md"
    r1 = manifest["representations"]["R1"]
    r2 = manifest["representations"]["R2"]
    cleaning = manifest["cleaning"]

    readme_content = f"""# ML Dataset v1.0

## Source
- Run ID: {manifest['source_run_id']}
- Source rows: {manifest['source_rows']}
- Acquisition tag: {manifest['acquisition_tag']}

## Representations

### R1: {', '.join(r1['features'])}
- Rows: {r1['rows']}
- SHA-256: {r1['sha256']}

### R2: {', '.join(r2['features'])}
- Rows: {r2['rows']}
- SHA-256: {r2['sha256']}

## Cleaning Summary
- Valid laptops: {cleaning['valid_laptop_count']}
- Excluded: {cleaning['excluded_count']}
- Ambiguous: {cleaning['ambiguous_count']}

## Files
- `r1_price_rating.parquet` — R1 matrix
- `r2_price_rating_review_count.parquet` — R2 matrix
- `cleaning_decisions.csv` — All decisions
- `excluded_observations.csv` — Excluded rows
- `ambiguous_observations.csv` — Ambiguous rows
- `ml_dataset_manifest.json` — Cryptographic manifest

## Git Commit
{manifest['git_commit']}
"""
    readme_path.write_text(readme_content, encoding="utf-8")
    return readme_path


def freeze_ml_dataset(
    *,
    run_id: str,
    config_path: Path,
    store: SQLiteStore,
    raw_jsonl_path: Path,
    readiness_json_path: Path,
    extreme_review_path: Path,
    missingness_review_path: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> FreezeResult:
    """Execute the full ML dataset freeze pipeline.

    Pipeline: load → eligibility → review semantics → decisions → matrices →
    validate → write artifacts → manifest → README.

    Uses atomic staging directory for writes.
    """
    # Load config
    config = load_ml_freeze_config(config_path)

    # Load all source data
    data = load_ml_freeze_input(
        run_id=run_id,
        store=store,
        raw_jsonl_path=raw_jsonl_path,
        readiness_json_path=readiness_json_path,
        extreme_review_path=extreme_review_path,
        missingness_review_path=missingness_review_path,
    )

    # Reconcile eligibility for each product
    eligibility_assessments = {}
    for _, row in data.products.iterrows():
        key = row["listing_key"]
        raw = data.raw_by_listing_key.get(key)
        assessment = assess_ml_eligibility(row=row, raw=raw, config=config)
        eligibility_assessments[key] = assessment

    # Reconcile review_count semantics
    review_resolutions = {}
    for _, row in data.products.iterrows():
        key = row["listing_key"]
        raw = data.raw_by_listing_key.get(key)
        # Get provenance rows for this product
        prov_rows = []
        if not data.provenance.empty and "listing_key" in data.provenance.columns:
            mask = data.provenance["listing_key"] == key
            prov_rows = data.provenance[mask].to_dict("records")
        resolution = resolve_review_count(
            row=row, raw=raw, provenance_rows=prov_rows, config=config
        )
        review_resolutions[key] = resolution

    # Build cleaning decisions
    decisions = []
    for _, row in data.products.iterrows():
        key = row["listing_key"]
        decision = build_cleaning_decision(
            row=row,
            eligibility=eligibility_assessments[key],
            review_resolution=review_resolutions[key],
        )
        decisions.append(decision)

    # Build matrices
    identity_columns = config.outputs.include_identity_columns
    matrices = build_ml_matrices(
        products=data.products,
        decisions=decisions,
        review_resolutions=review_resolutions,
        identity_columns=identity_columns,
    )

    # Validate
    validation = validate_frozen_matrices(
        source_products=data.products,
        matrices=matrices,
        decisions=decisions,
    )

    if not validation.passed:
        raise ValueError(
            f"Freeze validation failed with {len(validation.errors)} error(s): "
            + "; ".join(validation.errors[:5])
        )

    # Stage output
    staging_id = uuid.uuid4().hex[:8]
    artifact_name = config.artifact_name
    if dry_run:
        staging_dir = output_dir / "ml_freeze_preview"
    else:
        staging_dir = output_dir / f".staging-{staging_id}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Write Parquet
    r1_path = staging_dir / "r1_price_rating.parquet"
    r2_path = staging_dir / "r2_price_rating_review_count.parquet"
    pq.write_table(pa.Table.from_pandas(matrices.r1), r1_path)
    pq.write_table(pa.Table.from_pandas(matrices.r2), r2_path)

    # Check for baseline cleaning decisions for before/after diff
    baseline_dec_path = output_dir / "baseline_cleaning_decisions.csv"
    if not baseline_dec_path.exists():
        baseline_dec_path = output_dir / "ml-dataset-v1.0" / "cleaning_decisions.csv"

    # Write cleaning artifacts
    cleaning_path, excluded_path, ambiguous_path, _diff_path = write_cleaning_artifacts(
        decisions=decisions,
        review_resolutions=review_resolutions,
        products=data.products,
        output_dir=staging_dir,
        previous_cleaning_decisions_path=baseline_dec_path if baseline_dec_path.exists() else None,
    )

    # Build and write manifest
    source_paths = {
        "raw_jsonl": raw_jsonl_path,
        "readiness_json": readiness_json_path,
        "extreme_review": extreme_review_path,
        "missingness_review": missingness_review_path,
        "freeze_config": config_path,
    }
    artifact_paths_map = {
        "r1_parquet": r1_path,
        "r2_parquet": r2_path,
        "cleaning_decisions": cleaning_path,
        "excluded_observations": excluded_path,
        "ambiguous_observations": ambiguous_path,
    }

    git_commit = _get_git_commit()
    manifest = build_ml_dataset_manifest(
        run_id=run_id,
        config=config,
        matrices=matrices,
        decisions=decisions,
        source_paths=source_paths,
        artifact_paths=artifact_paths_map,
        git_commit=git_commit,
        acquisition_tag="dataset-acquisition-v1.0",
    )

    manifest_path = staging_dir / "ml_dataset_manifest.json"
    write_manifest(manifest, manifest_path)

    # Write README
    readme_path = _write_readme(staging_dir, manifest)

    # Atomic rename (skip for dry run — already in preview dir)
    if not dry_run:
        final_dir = output_dir / artifact_name
        if final_dir.exists():
            shutil.rmtree(final_dir)
        staging_dir.rename(final_dir)

        # Update paths to final location
        r1_path = final_dir / r1_path.name
        r2_path = final_dir / r2_path.name
        cleaning_path = final_dir / cleaning_path.name
        excluded_path = final_dir / excluded_path.name
        ambiguous_path = final_dir / ambiguous_path.name
        manifest_path = final_dir / manifest_path.name
        readme_path = final_dir / readme_path.name

    return FreezeResult(
        source_row_count=len(data.products),
        r1_rows=len(matrices.r1),
        r2_rows=len(matrices.r2),
        r1_path=r1_path,
        r2_path=r2_path,
        cleaning_decisions_path=cleaning_path,
        excluded_observations_path=excluded_path,
        ambiguous_observations_path=ambiguous_path,
        manifest_path=manifest_path,
        readme_path=readme_path,
    )
