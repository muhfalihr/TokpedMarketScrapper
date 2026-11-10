from datetime import UTC, datetime
from pathlib import Path

from tokped_market_scrapper.ml_readiness.association import analyze_associations
from tokped_market_scrapper.ml_readiness.complete_cases import analyze_all_representations
from tokped_market_scrapper.ml_readiness.distributions import analyze_all_distributions
from tokped_market_scrapper.ml_readiness.extremes import detect_extreme_prices
from tokped_market_scrapper.ml_readiness.integrity import audit_dataset_integrity
from tokped_market_scrapper.ml_readiness.loader import load_readiness_dataset
from tokped_market_scrapper.ml_readiness.missingness import analyze_missingness
from tokped_market_scrapper.ml_readiness.models import (
    AuditProvenance,
    MLReadinessConfig,
    MLReadinessReport,
    load_ml_readiness_config,
)
from tokped_market_scrapper.ml_readiness.representations import evaluate_all_representations
from tokped_market_scrapper.storage import SQLiteStore


def run_ml_readiness_audit(
    *,
    run_id: str,
    store: SQLiteStore,
    raw_jsonl_path: Path | str | None = None,
    config: MLReadinessConfig | None = None,
    git_commit: str = "unknown",
    acquisition_tag: str = "dataset-acquisition-v1.0",
    search_contract_sha256: str = "none",
    feature_audit_sha256: str = "none",
    readiness_config_sha256: str = "none",
) -> MLReadinessReport:
    """Orchestrate end-to-end ML dataset readiness audit across all pipeline stages."""
    if config is None:
        config = load_ml_readiness_config()

    # 1. Load dataset snapshot
    dataset = load_readiness_dataset(
        run_id=run_id,
        store=store,
        raw_jsonl_path=raw_jsonl_path,
    )
    dataset_rows = len(dataset.products)

    # 2. Audit dataset integrity
    integrity = audit_dataset_integrity(dataset)

    # 3. Analyze missingness
    missingness = analyze_missingness(dataset)

    # 4. Analyze complete cases for representations
    complete_cases = analyze_all_representations(dataset, config)

    # 5. Analyze feature distributions
    distributions = analyze_all_distributions(dataset.products, config)

    # 6. Detect extreme prices
    extreme_prices = detect_extreme_prices(dataset, config=config)

    # 7. Analyze pairwise feature associations
    associations = analyze_associations(
        dataset.products,
        features=tuple(config.features),
        spearman_redundancy_threshold=config.association.spearman_redundancy_threshold,
    )

    # 8. Evaluate representation readiness
    representations = evaluate_all_representations(
        config=config,
        integrity=integrity,
        complete_cases_dict=complete_cases,
        distributions=distributions,
        missingness=missingness,
        associations=associations,
        extreme_prices_count=len(extreme_prices),
    )

    # 9. Build provenance and assemble MLReadinessReport
    provenance = AuditProvenance(
        git_commit=git_commit,
        acquisition_tag=acquisition_tag,
        search_contract_sha256=search_contract_sha256,
        feature_audit_sha256=feature_audit_sha256,
        readiness_config_sha256=readiness_config_sha256,
    )

    return MLReadinessReport(
        run_id=run_id,
        generated_at=datetime.now(UTC).isoformat(),
        dataset_rows=dataset_rows,
        integrity=integrity,
        missingness=missingness,
        complete_cases=complete_cases,
        distributions=distributions,
        extreme_prices=extreme_prices,
        associations=associations,
        representations=representations,
        provenance=provenance,
    )
