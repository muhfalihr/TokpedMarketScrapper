"""Reproducibility manifest generation for Tokopedia searchProductV5 migration."""

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tokped_market_scrapper.config import load_search_config, load_seeds


def get_contract_sha256(contract_path: str | Path = "config/search_product_v5_contract.json") -> str:
    """Retrieve SHA256 of searchProductV5 GraphQL contract file."""
    path = Path(contract_path)
    if not path.exists():
        return "unknown"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "sha256" in data:
            return str(data["sha256"])
    except (json.JSONDecodeError, OSError):
        pass

    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


def get_file_sha256(path: str | Path) -> str:
    """Retrieve SHA256 hex digest of a file, or 'unknown' if file does not exist."""
    p = Path(path)
    if not p.exists():
        return "unknown"
    try:
        hasher = hashlib.sha256()
        hasher.update(p.read_bytes())
        return hasher.hexdigest()
    except OSError:
        return "unknown"


def generate_manifest(
    *,
    contract_path: str | Path = "config/search_product_v5_contract.json",
    seed_config: str | Path = "config/seeds.yaml",
    production_config: str | Path | None = "config/production.yaml",
    started_at: datetime | str | None = None,
    finished_at: datetime | str | None = None,
    seed_queries: list[str] | None = None,
    observed_total_data_min: int | None = None,
    observed_total_data_max: int | None = None,
    crawl_run_id: str | None = None,
    pipeline_meta: dict[str, Any] | None = None,
    acquisition_meta: dict[str, Any] | None = None,
    feature_audit_meta: dict[str, Any] | None = None,
    extra_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate reproducibility manifest data dict."""
    if started_at is None:
        started_at = datetime.now(UTC).isoformat()
    elif isinstance(started_at, datetime):
        started_at = started_at.isoformat()

    if finished_at is None:
        finished_at = datetime.now(UTC).isoformat()
    elif isinstance(finished_at, datetime):
        finished_at = finished_at.isoformat()

    # Load contract details
    contract_sha256 = get_contract_sha256(contract_path)

    # Load seed config details
    search_cfg = {}
    try:
        search_cfg = load_search_config(seed_config)
    except (OSError, ValueError, TypeError):
        pass

    if seed_queries is None:
        try:
            seeds = load_seeds(seed_config)
            seed_queries = [
                getattr(s, "query", "") for s in seeds if getattr(s, "query", None)
            ]
        except (OSError, ValueError, TypeError):
            seed_queries = []

    search_rows = search_cfg.get("rows", 60)
    search_category_sc = str(search_cfg.get("category_sc", "297"))
    search_sort_code = str(search_cfg.get("sort_code", "23"))

    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except (subprocess.SubprocessError, OSError):
        git_commit = "unknown"

    try:
        import scrapling
        scrapling_version = getattr(scrapling, "__version__", "unknown")
    except ImportError:
        scrapling_version = "unknown"

    manifest_data = {
        "search_operation": "searchProductV5",
        "search_contract_sha256": contract_sha256,
        "search_rows": search_rows,
        "search_category_sc": search_category_sc,
        "search_sort_code": search_sort_code,
        "seed_queries": seed_queries,
        "observed_total_data_min": observed_total_data_min,
        "observed_total_data_max": observed_total_data_max,
        "started_at": str(started_at),
        "finished_at": str(finished_at),
        "python_version": platform.python_version(),
        "scrapling_version": scrapling_version,
        "git_commit": git_commit,
    }

    if crawl_run_id:
        manifest_data["crawl_run_id"] = crawl_run_id

    if pipeline_meta is not None:
        p_meta = dict(pipeline_meta)
        if (
            "target_reached" not in p_meta
            and "actual_unique_eligible" in p_meta
            and "target_unique_eligible" in p_meta
        ):
            p_meta["target_reached"] = (
                p_meta["actual_unique_eligible"] >= p_meta["target_unique_eligible"]
            )
        manifest_data["pipeline"] = p_meta

    if acquisition_meta is not None:
        manifest_data["acquisition"] = acquisition_meta
    elif pipeline_meta is not None or (production_config and Path(production_config).exists()):
        acq_data = {
            "tag": "dataset-acquisition-v1.0",
            "commit": git_commit,
            "contract_sha256": contract_sha256,
            "seed_config_sha256": get_file_sha256(seed_config),
        }
        if production_config:
            acq_data["production_config_sha256"] = get_file_sha256(production_config)
        manifest_data["acquisition"] = acq_data

    if feature_audit_meta is not None:
        manifest_data["feature_audit"] = feature_audit_meta

    if extra_data:
        manifest_data.update(extra_data)

    return manifest_data


def write_manifest(
    crawl_dir: Path | str,
    manifest_data: dict[str, Any] | None = None,
    *args: Any,
    **kwargs: Any,
) -> Path:
    """Write reproducibility manifest.json to crawl_dir or output_dir."""
    # Support legacy positional signature: write_manifest(run_id, store, started_at, finished_at, output_dir)
    if isinstance(manifest_data, dict):
        target_dir = Path(crawl_dir)
        data = manifest_data
    else:
        # Legacy positional mode where crawl_dir is run_id
        run_id = str(crawl_dir)
        store = manifest_data
        started_at = args[0] if len(args) > 0 else kwargs.get("started_at")
        finished_at = args[1] if len(args) > 1 else kwargs.get("finished_at")
        target_dir = Path(args[2]) if len(args) > 2 else Path(kwargs.get("output_dir", "reports"))

        data = generate_manifest(
            crawl_run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
        )
        if store and hasattr(store, "get_all_products"):
            prods = store.get_all_products(run_id=run_id)
            rejs = store.count_rejected(run_id=run_id)
            data["raw_rows"] = len(prods)
            data["processed_rows"] = len(prods)
            data["rejected_rows"] = rejs

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return manifest_path
