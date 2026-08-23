"""Production capacity and yield preflight estimation module."""

import math
from pydantic import BaseModel


class CandidateBudgetEstimate(BaseModel):
    """Estimate of raw candidates and pages required to reach target unique eligible items."""

    target_unique_eligible: int
    eligibility_rate: float
    duplicate_rate: float
    safety_factor: float
    effective_yield_rate: float
    required_raw_candidates: int
    required_pages: int


class ProductionPreflightReport(BaseModel):
    """Preflight check report comparing required crawl capacity against configured limits."""

    target_unique_eligible: int
    observed_eligibility_rate: float
    observed_duplicate_rate: float
    estimate: CandidateBudgetEstimate
    configured_max_pages: int
    capacity_sufficient: bool
    warning: str | None = None


def estimate_candidate_budget(
    target_unique: int = 5000,
    eligibility_rate: float = 0.2517,
    duplicate_rate: float = 0.10,
    safety_factor: float = 1.20,
    rows_per_page: int = 60,
) -> CandidateBudgetEstimate:
    """Calculate the required raw candidate budget and search pages needed to reach target unique eligible items."""
    effective_yield_rate = eligibility_rate * (1.0 - duplicate_rate)
    required_raw_candidates = math.ceil((target_unique / effective_yield_rate) * safety_factor)
    required_pages = math.ceil(required_raw_candidates / rows_per_page)

    return CandidateBudgetEstimate(
        target_unique_eligible=target_unique,
        eligibility_rate=eligibility_rate,
        duplicate_rate=duplicate_rate,
        safety_factor=safety_factor,
        effective_yield_rate=effective_yield_rate,
        required_raw_candidates=required_raw_candidates,
        required_pages=required_pages,
    )


def run_production_preflight(
    target_unique: int = 5000,
    configured_max_pages: int = 500,
    observed_eligibility_rate: float = 0.2517,
    observed_duplicate_rate: float = 0.10,
) -> ProductionPreflightReport:
    """Run production capacity preflight check against configured max search pages."""
    estimate = estimate_candidate_budget(
        target_unique=target_unique,
        eligibility_rate=observed_eligibility_rate,
        duplicate_rate=observed_duplicate_rate,
    )

    capacity_sufficient = estimate.required_pages <= configured_max_pages
    warning = None
    if not capacity_sufficient:
        warning = (
            f"Insufficient crawl capacity: required {estimate.required_pages} pages "
            f"exceeds configured max_pages limit of {configured_max_pages}."
        )

    return ProductionPreflightReport(
        target_unique_eligible=target_unique,
        observed_eligibility_rate=observed_eligibility_rate,
        observed_duplicate_rate=observed_duplicate_rate,
        estimate=estimate,
        configured_max_pages=configured_max_pages,
        capacity_sufficient=capacity_sufficient,
        warning=warning,
    )
