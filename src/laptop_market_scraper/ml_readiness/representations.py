"""Module for evaluating ML representation readiness based on dataset audit findings."""

from collections.abc import Mapping, Sequence

from laptop_market_scraper.ml_readiness.models import (
    AssociationResult,
    CompleteCaseResult,
    DistributionResult,
    IntegrityResult,
    MLReadinessConfig,
    MissingnessResult,
    MissingSemanticStatus,
    RepresentationReadiness,
    RepresentationStatus,
)


def evaluate_representation(
    *,
    representation_id: str,
    features: tuple[str, ...],
    integrity: IntegrityResult,
    complete_cases: CompleteCaseResult,
    distributions: Mapping[str, DistributionResult],
    missingness: MissingnessResult,
    associations: tuple[AssociationResult, ...] | Sequence[AssociationResult],
    extreme_prices_count: int = 0,
) -> RepresentationReadiness:
    """Evaluate readiness status for a candidate representation according to audit policy."""
    caveats: list[str] = []

    # 1. NOT_READY conditions
    not_ready = False

    # Check integrity failures affecting required features or general dataset integrity
    if not integrity.passed:
        failed_features = []
        for feat in features:
            if feat in integrity.missing_required_columns:
                failed_features.append(feat)
            elif feat == "price" and len(integrity.invalid_price_keys) > 0:
                failed_features.append(feat)
            elif feat == "rating" and len(integrity.invalid_rating_keys) > 0:
                failed_features.append(feat)
            elif feat == "review_count" and len(integrity.invalid_review_count_keys) > 0:
                failed_features.append(feat)

        if failed_features:
            not_ready = True
            caveats.append(f"Integrity check failed for required feature(s): {', '.join(failed_features)}")
        else:
            not_ready = True
            caveats.append("Dataset integrity check failed")

    # Check zero complete cases
    if complete_cases.complete_rows == 0:
        not_ready = True
        caveats.append("Zero complete cases remaining for representation")

    # Check zero variance
    for feat in features:
        dist = distributions.get(feat)
        if dist is not None and dist.zero_variance_flag:
            not_ready = True
            caveats.append(f"Zero variance detected for required feature '{feat}'")

    if not_ready:
        dedup_caveats = tuple(dict.fromkeys(caveats))
        return RepresentationReadiness(
            representation_id=representation_id,
            required_features=tuple(features),
            status=RepresentationStatus.NOT_READY,
            caveats=dedup_caveats,
            complete_rows=complete_cases.complete_rows,
            retention_percent=complete_cases.retention_percent,
        )

    # 2. REVIEW_REQUIRED conditions
    review_required = False

    if "review_count" in features and missingness.missing_reviews_only > 0:
        review_required = True
        caveats.append(
            f"Unresolved missing-value semantics for review_count "
            f"(missing_reviews_only = {missingness.missing_reviews_only})"
        )

    for case in missingness.cases:
        if case.semantic_status in (
            MissingSemanticStatus.UNRESOLVED,
            MissingSemanticStatus.AMBIGUOUS,
        ):
            if case.rating_missing and "rating" in features:
                review_required = True
                caveats.append(
                    f"Unresolved or ambiguous missingness semantics for rating (listing {case.listing_key})"
                )
            if case.review_count_missing and "review_count" in features:
                review_required = True
                caveats.append(
                    f"Unresolved or ambiguous missingness semantics for review_count (listing {case.listing_key})"
                )

    if review_required:
        dedup_caveats = tuple(dict.fromkeys(caveats))
        return RepresentationReadiness(
            representation_id=representation_id,
            required_features=tuple(features),
            status=RepresentationStatus.REVIEW_REQUIRED,
            caveats=dedup_caveats,
            complete_rows=complete_cases.complete_rows,
            retention_percent=complete_cases.retention_percent,
        )

    # 3. READY_WITH_CAVEATS conditions
    ready_with_caveats = False

    if complete_cases.retention_percent < 90.0:
        ready_with_caveats = True
        caveats.append(
            f"Complete-case retention below 90% ({complete_cases.retention_percent:.1f}%)"
        )

    for assoc in associations:
        if (
            assoc.redundancy_review
            and assoc.feature_a in features
            and assoc.feature_b in features
        ):
            ready_with_caveats = True
            rho_str = f"rho={assoc.spearman_rho:.2f}" if assoc.spearman_rho is not None else ""
            caveats.append(
                f"Strong Spearman redundancy detected between {assoc.feature_a} and {assoc.feature_b} ({rho_str})"
            )

    for feat in features:
        dist = distributions.get(feat)
        if dist is not None:
            dom_rate = dist.dominant_value_rate
            rate_pct = dom_rate * 100.0 if dom_rate <= 1.0 else dom_rate
            if rate_pct >= 90.0:
                ready_with_caveats = True
                caveats.append(
                    f"Dominant value rate >= 90.0% for feature '{feat}' ({rate_pct:.1f}%)"
                )

    if "price" in features and extreme_prices_count > 0:
        ready_with_caveats = True
        caveats.append(
            f"Extreme price observations pending review (count: {extreme_prices_count})"
        )

    if ready_with_caveats:
        dedup_caveats = tuple(dict.fromkeys(caveats))
        return RepresentationReadiness(
            representation_id=representation_id,
            required_features=tuple(features),
            status=RepresentationStatus.READY_WITH_CAVEATS,
            caveats=dedup_caveats,
            complete_rows=complete_cases.complete_rows,
            retention_percent=complete_cases.retention_percent,
        )

    # 4. READY
    return RepresentationReadiness(
        representation_id=representation_id,
        required_features=tuple(features),
        status=RepresentationStatus.READY,
        caveats=(),
        complete_rows=complete_cases.complete_rows,
        retention_percent=complete_cases.retention_percent,
    )


def evaluate_all_representations(
    config: MLReadinessConfig,
    integrity: IntegrityResult,
    complete_cases_dict: Mapping[str, CompleteCaseResult],
    distributions: Mapping[str, DistributionResult],
    missingness: MissingnessResult,
    associations: tuple[AssociationResult, ...] | Sequence[AssociationResult],
    extreme_prices_count: int = 0,
) -> dict[str, RepresentationReadiness]:
    """Evaluate readiness status for all candidate representations defined in config."""
    readiness_map: dict[str, RepresentationReadiness] = {}
    for rep_id, rep_cfg in config.representations.items():
        complete_case_res = complete_cases_dict.get(
            rep_id,
            CompleteCaseResult(
                representation_id=rep_id,
                required_features=tuple(rep_cfg.features),
                total_rows=0,
                complete_rows=0,
                dropped_rows=0,
                retention_percent=0.0,
                dropped_percent=0.0,
                complete_listing_keys=(),
            ),
        )
        readiness_map[rep_id] = evaluate_representation(
            representation_id=rep_id,
            features=tuple(rep_cfg.features),
            integrity=integrity,
            complete_cases=complete_case_res,
            distributions=distributions,
            missingness=missingness,
            associations=associations,
            extreme_prices_count=extreme_prices_count,
        )
    return readiness_map
