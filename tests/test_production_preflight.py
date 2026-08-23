"""Unit tests for production capacity/yield preflight module."""

from laptop_market_scraper.pipeline.preflight import (
    CandidateBudgetEstimate,
    ProductionPreflightReport,
    estimate_candidate_budget,
    run_production_preflight,
)


def test_estimate_candidate_budget_default_parameters():
    """Test candidate budget estimation with default parameters for target 5000."""
    estimate = estimate_candidate_budget()

    assert isinstance(estimate, CandidateBudgetEstimate)
    assert estimate.target_unique_eligible == 5000
    assert estimate.eligibility_rate == 0.2517
    assert estimate.duplicate_rate == 0.10
    assert estimate.safety_factor == 1.20
    assert abs(estimate.effective_yield_rate - (0.2517 * 0.90)) < 1e-6
    # For target 5000: required_raw_candidates should be > 20000 (specifically 26487)
    assert estimate.required_raw_candidates > 20000
    assert estimate.required_raw_candidates == 26487
    assert estimate.required_pages == 442


def test_run_production_preflight_sufficient_capacity():
    """Test run_production_preflight when configured_max_pages is sufficient (500)."""
    report = run_production_preflight(
        target_unique=5000,
        configured_max_pages=500,
        observed_eligibility_rate=0.2517,
        observed_duplicate_rate=0.10,
    )

    assert isinstance(report, ProductionPreflightReport)
    assert report.target_unique_eligible == 5000
    assert report.observed_eligibility_rate == 0.2517
    assert report.observed_duplicate_rate == 0.10
    assert report.configured_max_pages == 500
    assert report.capacity_sufficient is True
    assert report.warning is None
    assert report.estimate.required_pages == 442


def test_run_production_preflight_insufficient_capacity():
    """Test run_production_preflight when configured_max_pages is insufficient (100)."""
    report = run_production_preflight(
        target_unique=5000,
        configured_max_pages=100,
        observed_eligibility_rate=0.2517,
        observed_duplicate_rate=0.10,
    )

    assert isinstance(report, ProductionPreflightReport)
    assert report.capacity_sufficient is False
    assert report.warning is not None
    assert "exceeds" in report.warning or "insufficient" in report.warning.lower() or "100" in report.warning
