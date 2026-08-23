import pytest

from laptop_market_scraper.ml_readiness.models import (
    AssociationConfig,
    AssociationResult,
    CompleteCaseResult,
    DistributionResult,
    ExtremesConfig,
    IntegrityResult,
    MLReadinessConfig,
    MissingnessCase,
    MissingnessResult,
    MissingSemanticStatus,
    RepresentationConfig,
    RepresentationReadiness,
    RepresentationStatus,
    TransformationSignal,
)
from laptop_market_scraper.ml_readiness.representations import (
    evaluate_all_representations,
    evaluate_representation,
)


@pytest.fixture
def clean_integrity() -> IntegrityResult:
    return IntegrityResult(
        normalized_rows=100,
        raw_rows=100,
        unique_normalized_keys=100,
        unique_raw_keys=100,
        duplicate_normalized_keys=(),
        orphan_normalized_records=0,
        orphan_raw_records=0,
        missing_required_columns=(),
        invalid_price_keys=(),
        invalid_rating_keys=(),
        invalid_review_count_keys=(),
        passed=True,
    )


@pytest.fixture
def clean_complete_cases_r1() -> CompleteCaseResult:
    return CompleteCaseResult(
        representation_id="r1",
        required_features=("price", "rating"),
        total_rows=100,
        complete_rows=95,
        dropped_rows=5,
        retention_percent=95.0,
        dropped_percent=5.0,
        complete_listing_keys=tuple(f"k{i}" for i in range(95)),
    )


@pytest.fixture
def clean_complete_cases_r2() -> CompleteCaseResult:
    return CompleteCaseResult(
        representation_id="r2",
        required_features=("price", "rating", "review_count"),
        total_rows=100,
        complete_rows=92,
        dropped_rows=8,
        retention_percent=92.0,
        dropped_percent=8.0,
        complete_listing_keys=tuple(f"k{i}" for i in range(92)),
    )


@pytest.fixture
def clean_distributions() -> dict[str, DistributionResult]:
    return {
        "price": DistributionResult(
            feature_name="price",
            non_null_count=100,
            missing_count=0,
            coverage_percent=100.0,
            min_value=5000000.0,
            q01=6000000.0,
            q25=10000000.0,
            median=15000000.0,
            q75=20000000.0,
            q99=40000000.0,
            max_value=50000000.0,
            iqr=10000000.0,
            raw_skewness=1.1,
            log1p_skewness=0.2,
            absolute_skew_reduction=0.9,
            variance=2.5e13,
            std_dev=5000000.0,
            zero_count=0,
            zero_rate=0.0,
            unique_value_count=80,
            dominant_value_count=5,
            dominant_value_rate=0.05,
            zero_variance_flag=False,
            near_zero_variance_flag=False,
            transformation_signal=TransformationSignal.LOG1P_RECOMMENDED,
        ),
        "rating": DistributionResult(
            feature_name="rating",
            non_null_count=95,
            missing_count=5,
            coverage_percent=95.0,
            min_value=3.0,
            q01=3.5,
            q25=4.2,
            median=4.6,
            q75=4.8,
            q99=5.0,
            max_value=5.0,
            iqr=0.6,
            raw_skewness=-0.5,
            log1p_skewness=None,
            absolute_skew_reduction=None,
            variance=0.15,
            std_dev=0.38,
            zero_count=0,
            zero_rate=0.0,
            unique_value_count=20,
            dominant_value_count=15,
            dominant_value_rate=0.15,
            zero_variance_flag=False,
            near_zero_variance_flag=False,
            transformation_signal=TransformationSignal.NOT_APPLICABLE,
        ),
        "review_count": DistributionResult(
            feature_name="review_count",
            non_null_count=92,
            missing_count=8,
            coverage_percent=92.0,
            min_value=0.0,
            q01=0.0,
            q25=2.0,
            median=10.0,
            q75=50.0,
            q99=500.0,
            max_value=1000.0,
            iqr=48.0,
            raw_skewness=3.2,
            log1p_skewness=0.4,
            absolute_skew_reduction=2.8,
            variance=1500.0,
            std_dev=38.7,
            zero_count=10,
            zero_rate=0.108,
            unique_value_count=40,
            dominant_value_count=12,
            dominant_value_rate=0.13,
            zero_variance_flag=False,
            near_zero_variance_flag=False,
            transformation_signal=TransformationSignal.LOG1P_RECOMMENDED,
        ),
    }


@pytest.fixture
def clean_missingness() -> MissingnessResult:
    return MissingnessResult(
        total_rows=100,
        complete_rating_and_reviews=92,
        missing_rating_only=3,
        missing_reviews_only=0,
        missing_both=5,
        rating_missing_percent=8.0,
        review_missing_percent=5.0,
        cases=(),
    )


@pytest.fixture
def clean_associations() -> tuple[AssociationResult, ...]:
    return (
        AssociationResult(
            feature_a="price",
            feature_b="rating",
            pairwise_n=95,
            spearman_rho=0.25,
            pearson_r=0.22,
            strength="weak",
            redundancy_review=False,
        ),
        AssociationResult(
            feature_a="price",
            feature_b="review_count",
            pairwise_n=92,
            spearman_rho=0.40,
            pearson_r=0.35,
            strength="moderate",
            redundancy_review=False,
        ),
        AssociationResult(
            feature_a="rating",
            feature_b="review_count",
            pairwise_n=92,
            spearman_rho=0.55,
            pearson_r=0.50,
            strength="moderate",
            redundancy_review=False,
        ),
    )


def test_evaluate_representation_r1_ready(
    clean_integrity: IntegrityResult,
    clean_complete_cases_r1: CompleteCaseResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
    clean_associations: tuple[AssociationResult, ...],
):
    result = evaluate_representation(
        representation_id="r1",
        features=("price", "rating"),
        integrity=clean_integrity,
        complete_cases=clean_complete_cases_r1,
        distributions=clean_distributions,
        missingness=clean_missingness,
        associations=clean_associations,
        extreme_prices_count=0,
    )

    assert isinstance(result, RepresentationReadiness)
    assert result.representation_id == "r1"
    assert result.required_features == ("price", "rating")
    assert result.status == RepresentationStatus.READY
    assert result.caveats == ()
    assert result.complete_rows == 95
    assert result.retention_percent == 95.0


def test_evaluate_representation_r2_review_required(
    clean_integrity: IntegrityResult,
    clean_complete_cases_r2: CompleteCaseResult,
    clean_distributions: dict[str, DistributionResult],
    clean_associations: tuple[AssociationResult, ...],
):
    missingness = MissingnessResult(
        total_rows=100,
        complete_rating_and_reviews=90,
        missing_rating_only=2,
        missing_reviews_only=4,  # Ambiguous missingness case for review_count
        missing_both=4,
        rating_missing_percent=6.0,
        review_missing_percent=8.0,
        cases=(
            MissingnessCase(
                listing_key="k10",
                product_name="Test Product",
                product_url=None,
                rating=4.5,
                review_count=None,
                rating_missing=False,
                review_count_missing=True,
                semantic_status=MissingSemanticStatus.AMBIGUOUS,
                evidence=("Rating present but review count is missing",),
            ),
        ),
    )

    result = evaluate_representation(
        representation_id="r2",
        features=("price", "rating", "review_count"),
        integrity=clean_integrity,
        complete_cases=clean_complete_cases_r2,
        distributions=clean_distributions,
        missingness=missingness,
        associations=clean_associations,
        extreme_prices_count=0,
    )

    assert result.status == RepresentationStatus.REVIEW_REQUIRED
    assert len(result.caveats) > 0
    assert any("review_count" in c for c in result.caveats)


def test_evaluate_representation_not_ready_zero_complete_cases(
    clean_integrity: IntegrityResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
    clean_associations: tuple[AssociationResult, ...],
):
    zero_cases = CompleteCaseResult(
        representation_id="r1",
        required_features=("price", "rating"),
        total_rows=100,
        complete_rows=0,
        dropped_rows=100,
        retention_percent=0.0,
        dropped_percent=100.0,
        complete_listing_keys=(),
    )

    result = evaluate_representation(
        representation_id="r1",
        features=("price", "rating"),
        integrity=clean_integrity,
        complete_cases=zero_cases,
        distributions=clean_distributions,
        missingness=clean_missingness,
        associations=clean_associations,
    )

    assert result.status == RepresentationStatus.NOT_READY
    assert any("retention" in c.lower() or "cases" in c.lower() for c in result.caveats)


def test_evaluate_representation_not_ready_zero_variance(
    clean_integrity: IntegrityResult,
    clean_complete_cases_r1: CompleteCaseResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
    clean_associations: tuple[AssociationResult, ...],
):
    distributions = dict(clean_distributions)
    distributions["rating"] = DistributionResult(
        feature_name="rating",
        non_null_count=100,
        missing_count=0,
        coverage_percent=100.0,
        min_value=5.0,
        q01=5.0,
        q25=5.0,
        median=5.0,
        q75=5.0,
        q99=5.0,
        max_value=5.0,
        iqr=0.0,
        raw_skewness=None,
        log1p_skewness=None,
        absolute_skew_reduction=None,
        variance=0.0,
        std_dev=0.0,
        zero_count=0,
        zero_rate=0.0,
        unique_value_count=1,
        dominant_value_count=100,
        dominant_value_rate=1.0,
        zero_variance_flag=True,
        near_zero_variance_flag=True,
        transformation_signal=TransformationSignal.NOT_APPLICABLE,
    )

    result = evaluate_representation(
        representation_id="r1",
        features=("price", "rating"),
        integrity=clean_integrity,
        complete_cases=clean_complete_cases_r1,
        distributions=distributions,
        missingness=clean_missingness,
        associations=clean_associations,
    )

    assert result.status == RepresentationStatus.NOT_READY
    assert any("variance" in c.lower() for c in result.caveats)


def test_evaluate_representation_not_ready_integrity_failure(
    clean_complete_cases_r1: CompleteCaseResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
    clean_associations: tuple[AssociationResult, ...],
):
    failed_integrity = IntegrityResult(
        normalized_rows=100,
        raw_rows=100,
        unique_normalized_keys=100,
        unique_raw_keys=100,
        duplicate_normalized_keys=(),
        orphan_normalized_records=0,
        orphan_raw_records=0,
        missing_required_columns=("price",),
        invalid_price_keys=("k1",),
        invalid_rating_keys=(),
        invalid_review_count_keys=(),
        passed=False,
    )

    result = evaluate_representation(
        representation_id="r1",
        features=("price", "rating"),
        integrity=failed_integrity,
        complete_cases=clean_complete_cases_r1,
        distributions=clean_distributions,
        missingness=clean_missingness,
        associations=clean_associations,
    )

    assert result.status == RepresentationStatus.NOT_READY
    assert any("integrity" in c.lower() or "price" in c.lower() for c in result.caveats)


def test_evaluate_representation_ready_with_caveats_low_retention(
    clean_integrity: IntegrityResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
    clean_associations: tuple[AssociationResult, ...],
):
    low_retention_cases = CompleteCaseResult(
        representation_id="r1",
        required_features=("price", "rating"),
        total_rows=100,
        complete_rows=85,
        dropped_rows=15,
        retention_percent=85.0,
        dropped_percent=15.0,
        complete_listing_keys=tuple(f"k{i}" for i in range(85)),
    )

    result = evaluate_representation(
        representation_id="r1",
        features=("price", "rating"),
        integrity=clean_integrity,
        complete_cases=low_retention_cases,
        distributions=clean_distributions,
        missingness=clean_missingness,
        associations=clean_associations,
    )

    assert result.status == RepresentationStatus.READY_WITH_CAVEATS
    assert any("retention" in c.lower() for c in result.caveats)


def test_evaluate_representation_ready_with_caveats_redundancy(
    clean_integrity: IntegrityResult,
    clean_complete_cases_r1: CompleteCaseResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
):
    redundant_associations = (
        AssociationResult(
            feature_a="price",
            feature_b="rating",
            pairwise_n=95,
            spearman_rho=0.92,
            pearson_r=0.90,
            strength="strong",
            redundancy_review=True,
        ),
    )

    result = evaluate_representation(
        representation_id="r1",
        features=("price", "rating"),
        integrity=clean_integrity,
        complete_cases=clean_complete_cases_r1,
        distributions=clean_distributions,
        missingness=clean_missingness,
        associations=redundant_associations,
    )

    assert result.status == RepresentationStatus.READY_WITH_CAVEATS
    assert any("redundancy" in c.lower() or "spearman" in c.lower() for c in result.caveats)


def test_evaluate_representation_ready_with_caveats_extreme_prices(
    clean_integrity: IntegrityResult,
    clean_complete_cases_r1: CompleteCaseResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
    clean_associations: tuple[AssociationResult, ...],
):
    result = evaluate_representation(
        representation_id="r1",
        features=("price", "rating"),
        integrity=clean_integrity,
        complete_cases=clean_complete_cases_r1,
        distributions=clean_distributions,
        missingness=clean_missingness,
        associations=clean_associations,
        extreme_prices_count=4,
    )

    assert result.status == RepresentationStatus.READY_WITH_CAVEATS
    assert any("extreme" in c.lower() or "price" in c.lower() for c in result.caveats)


def test_evaluate_all_representations(
    clean_integrity: IntegrityResult,
    clean_complete_cases_r1: CompleteCaseResult,
    clean_complete_cases_r2: CompleteCaseResult,
    clean_distributions: dict[str, DistributionResult],
    clean_missingness: MissingnessResult,
    clean_associations: tuple[AssociationResult, ...],
):
    config = MLReadinessConfig(
        features=["price", "rating", "review_count"],
        representations={
            "r1": RepresentationConfig(
                id="r1", description="R1", features=["price", "rating"]
            ),
            "r2": RepresentationConfig(
                id="r2", description="R2", features=["price", "rating", "review_count"]
            ),
        },
        extremes=ExtremesConfig(
            price_lower_quantile=0.01,
            price_upper_quantile=0.99,
            iqr_multiplier=1.5,
            robust_z_threshold=3.5,
            sample_limit=10,
        ),
        association=AssociationConfig(spearman_redundancy_threshold=0.85),
    )

    complete_cases_dict = {
        "r1": clean_complete_cases_r1,
        "r2": clean_complete_cases_r2,
    }

    all_readiness = evaluate_all_representations(
        config=config,
        integrity=clean_integrity,
        complete_cases_dict=complete_cases_dict,
        distributions=clean_distributions,
        missingness=clean_missingness,
        associations=clean_associations,
        extreme_prices_count=0,
    )

    assert set(all_readiness.keys()) == {"r1", "r2"}
    assert all_readiness["r1"].status == RepresentationStatus.READY
    assert all_readiness["r2"].status == RepresentationStatus.READY
