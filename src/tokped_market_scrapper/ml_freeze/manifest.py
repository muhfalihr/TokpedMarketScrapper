"""Generate cryptographic freeze manifest for ML dataset artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tokped_market_scrapper.ml_freeze.matrices import FrozenMatrices
from tokped_market_scrapper.ml_freeze.models import (
    CleaningDecision,
    EligibilityDecision,
    MLFreezeConfig,
    ReviewCountSemanticStatus,
)


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def build_ml_dataset_manifest(
    *,
    run_id: str,
    config: MLFreezeConfig,
    matrices: FrozenMatrices,
    decisions: Sequence[CleaningDecision],
    source_paths: Mapping[str, Path],
    artifact_paths: Mapping[str, Path],
    git_commit: str,
    acquisition_tag: str,
    review_gate: Any | None = None,
    review_decisions_path: Path | None = None,
) -> dict[str, Any]:
    """Build a comprehensive freeze manifest with cryptographic hashes.

    The manifest captures the full provenance chain from source to output.
    """
    # Count eligibility decisions
    decision_counts: Counter[str] = Counter()
    exclusion_reason_counts: Counter[str] = Counter()
    review_status_counts: Counter[str] = Counter()

    for d in decisions:
        decision_counts[d.eligibility_decision.value] += 1
        if d.eligibility_decision == EligibilityDecision.EXCLUDE:
            exclusion_reason_counts[d.eligibility_reason.value] += 1
        review_status_counts[d.review_count_status.value] += 1

    # Hash source files
    source_hashes = {}
    for name, path in source_paths.items():
        if path.exists():
            source_hashes[name] = _sha256_file(path)

    # Hash artifact files
    artifact_hashes = {}
    for name, path in artifact_paths.items():
        if path.exists():
            artifact_hashes[name] = _sha256_file(path)

    # Hash config
    config_json = config.model_dump_json()
    config_hash = _sha256_bytes(config_json.encode("utf-8"))

    manifest = {
        "artifact": config.artifact_name,
        "source_run_id": run_id,
        "source_rows": len(decisions),
        "representations": {
            "R1": {
                "features": list(config.representations["R1"].features),
                "rows": len(matrices.r1),
                "sha256": artifact_hashes.get("r1_parquet", ""),
            },
            "R2": {
                "features": list(config.representations["R2"].features),
                "rows": len(matrices.r2),
                "sha256": artifact_hashes.get("r2_parquet", ""),
            },
        },
        "cleaning": {
            "valid_laptop_count": decision_counts.get(
                EligibilityDecision.VALID_LAPTOP.value, 0
            ),
            "excluded_count": decision_counts.get(
                EligibilityDecision.EXCLUDE.value, 0
            ),
            "ambiguous_count": decision_counts.get(
                EligibilityDecision.AMBIGUOUS.value, 0
            ),
            "exclusion_reason_counts": dict(exclusion_reason_counts),
            "review_count_semantics": {
                "observed_count": review_status_counts.get(
                    ReviewCountSemanticStatus.OBSERVED_COUNT.value, 0
                ),
                "explicit_zero": review_status_counts.get(
                    ReviewCountSemanticStatus.EXPLICIT_ZERO.value, 0
                ),
                "semantic_zero_proven": review_status_counts.get(
                    ReviewCountSemanticStatus.SEMANTIC_ZERO_PROVEN.value, 0
                ),
                "missing_unresolved": review_status_counts.get(
                    ReviewCountSemanticStatus.MISSING_UNRESOLVED.value, 0
                ),
            },
        },
        "source_hashes": source_hashes,
        "artifact_hashes": artifact_hashes,
        "git_commit": git_commit,
        "acquisition_tag": acquisition_tag,
        "freeze_config_sha256": config_hash,
    }

    if review_gate is not None or (review_decisions_path and review_decisions_path.exists()):
        sha = _sha256_file(review_decisions_path) if review_decisions_path and review_decisions_path.exists() else ""
        manifest["release_review"] = {
            "low_price_review_required": getattr(review_gate, "total_required", 20),
            "low_price_review_resolved": getattr(review_gate, "total_resolved", 20),
            "approved_valid": getattr(review_gate, "approved_valid", 0),
            "leakage": getattr(review_gate, "leakage", 0),
            "ambiguous": getattr(review_gate, "ambiguous", 0),
            "review_decisions_sha256": sha,
        }

    return manifest


def write_manifest(manifest: dict[str, Any], output_path: Path) -> Path:
    """Write manifest as pretty-printed JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return output_path
