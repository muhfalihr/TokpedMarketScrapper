import pandas as pd

from tokped_market_scrapper.ml_readiness.loader import ReadinessDataset
from tokped_market_scrapper.ml_readiness.models import (
    CompleteCaseResult,
    MLReadinessConfig,
)


def analyze_complete_cases(
    dataset: ReadinessDataset,
    *,
    representation_id: str,
    required_features: tuple[str, ...],
) -> CompleteCaseResult:
    """Analyze complete-case retention and dropped rows for a specific feature representation."""
    df = dataset.products
    total_rows = len(df)

    if total_rows == 0:
        return CompleteCaseResult(
            representation_id=representation_id,
            required_features=tuple(required_features),
            total_rows=0,
            complete_rows=0,
            dropped_rows=0,
            retention_percent=0.0,
            dropped_percent=0.0,
            complete_listing_keys=(),
        )

    missing_cols = set(required_features) - set(df.columns)
    if missing_cols:
        complete_df = df.iloc[0:0]
    else:
        complete_df = df.dropna(subset=list(required_features))

    complete_rows = len(complete_df)
    dropped_rows = total_rows - complete_rows

    retention_percent = (complete_rows / total_rows) * 100.0 if total_rows > 0 else 0.0
    dropped_percent = (dropped_rows / total_rows) * 100.0 if total_rows > 0 else 0.0

    if "listing_key" in complete_df.columns:
        keys = sorted(str(k) for k in complete_df["listing_key"] if pd.notna(k))
        complete_listing_keys = tuple(keys)
    else:
        complete_listing_keys = ()

    return CompleteCaseResult(
        representation_id=representation_id,
        required_features=tuple(required_features),
        total_rows=total_rows,
        complete_rows=complete_rows,
        dropped_rows=dropped_rows,
        retention_percent=retention_percent,
        dropped_percent=dropped_percent,
        complete_listing_keys=complete_listing_keys,
    )


def analyze_all_representations(
    dataset: ReadinessDataset, config: MLReadinessConfig
) -> dict[str, CompleteCaseResult]:
    """Analyze complete cases for all representations defined in configuration."""
    results: dict[str, CompleteCaseResult] = {}
    for rep_id, rep_config in config.representations.items():
        results[rep_id] = analyze_complete_cases(
            dataset,
            representation_id=rep_id,
            required_features=tuple(rep_config.features),
        )
    return results


audit_complete_cases = analyze_complete_cases
