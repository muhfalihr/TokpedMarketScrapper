import itertools

import pandas as pd

from laptop_market_scraper.ml_readiness.models import (
    REQUIRED_FEATURES,
    AssociationResult,
)


def analyze_associations(
    products: pd.DataFrame,
    *,
    features: tuple[str, ...] = REQUIRED_FEATURES,
    spearman_redundancy_threshold: float = 0.85,
) -> tuple[AssociationResult, ...]:
    """Analyze pairwise feature associations using Spearman correlation, supplemental Pearson correlation,

    and redundancy flags.
    """
    results: list[AssociationResult] = []

    for feature_a, feature_b in itertools.combinations(features, 2):
        if feature_a in products.columns and feature_b in products.columns:
            s_a = pd.to_numeric(products[feature_a], errors="coerce")
            s_b = pd.to_numeric(products[feature_b], errors="coerce")
            pair_df = pd.DataFrame({feature_a: s_a, feature_b: s_b}).dropna()
        else:
            pair_df = pd.DataFrame(columns=[feature_a, feature_b])

        pairwise_n = len(pair_df)

        if pairwise_n < 3:
            results.append(
                AssociationResult(
                    feature_a=feature_a,
                    feature_b=feature_b,
                    pairwise_n=pairwise_n,
                    spearman_rho=None,
                    pearson_r=None,
                    strength=None,
                    redundancy_review=False,
                )
            )
            continue

        var_a = pair_df[feature_a].var()
        var_b = pair_df[feature_b].var()
        nunique_a = pair_df[feature_a].nunique()
        nunique_b = pair_df[feature_b].nunique()

        if pd.isna(var_a) or pd.isna(var_b) or var_a == 0.0 or var_b == 0.0 or nunique_a <= 1 or nunique_b <= 1:
            results.append(
                AssociationResult(
                    feature_a=feature_a,
                    feature_b=feature_b,
                    pairwise_n=pairwise_n,
                    spearman_rho=None,
                    pearson_r=None,
                    strength=None,
                    redundancy_review=False,
                )
            )
            continue

        rank_a = pair_df[feature_a].rank()
        rank_b = pair_df[feature_b].rank()
        spearman_calc = rank_a.corr(rank_b, method="pearson")
        pearson_calc = pair_df[feature_a].corr(pair_df[feature_b], method="pearson")


        if pd.isna(spearman_calc):
            results.append(
                AssociationResult(
                    feature_a=feature_a,
                    feature_b=feature_b,
                    pairwise_n=pairwise_n,
                    spearman_rho=None,
                    pearson_r=None,
                    strength=None,
                    redundancy_review=False,
                )
            )
            continue

        spearman_rho = float(spearman_calc)
        pearson_r = float(pearson_calc) if not pd.isna(pearson_calc) else None

        abs_rho = abs(spearman_rho)
        if abs_rho < 0.30:
            strength = "weak"
        elif abs_rho < 0.70:
            strength = "moderate"
        else:
            strength = "strong"

        redundancy_review = abs_rho >= spearman_redundancy_threshold

        results.append(
            AssociationResult(
                feature_a=feature_a,
                feature_b=feature_b,
                pairwise_n=pairwise_n,
                spearman_rho=spearman_rho,
                pearson_r=pearson_r,
                strength=strength,
                redundancy_review=redundancy_review,
            )
        )

    return tuple(results)


audit_associations = analyze_associations
