"""Laptop-vs-accessory classification rules."""

from typing import Any

from pydantic import BaseModel

from laptop_market_scraper.models import SearchProduct

ALLOWED_BREADCRUMB_PREFIXES: tuple[str, ...] = ("komputer-laptop/laptop/",)
ALLOWED_BREADCRUMB_EXACT: set[str] = {"komputer-laptop/pc-laptop-gaming/laptop-gaming"}

NEGATIVE_TITLE_KEYWORDS: set[str] = {
    "tas laptop",
    "charger laptop",
    "adaptor laptop",
    "adapter laptop",
    "cooling pad",
    "stand laptop",
    "sleeve laptop",
    "skin laptop",
    "stiker laptop",
    "casing laptop",
    "keyboard laptop",
    "lcd laptop",
    "layar laptop",
    "baterai laptop",
    "battery laptop",
    "fan laptop",
    "engsel laptop",
    "screen protector",
    "mouse laptop",
}

_POSITIVE_TITLE_TERMS: frozenset[str] = frozenset({
    "laptop",
    "notebook",
    "ultrabook",
    "chromebook",
    "macbook",
})


class EligibilityResult(BaseModel):
    accepted: bool
    reason: str


def _extract_breadcrumb_and_name(product: SearchProduct | dict[str, Any] | Any) -> tuple[str, str]:
    if isinstance(product, SearchProduct):
        breadcrumb = product.category.breadcrumb or ""
        name = product.name or ""
    elif isinstance(product, dict):
        breadcrumb = ""
        cat = product.get("category")
        if isinstance(cat, dict):
            breadcrumb = cat.get("breadcrumb") or ""
        elif isinstance(cat, str):
            breadcrumb = cat

        if not breadcrumb:
            bc = (
                product.get("breadcrumb")
                or product.get("breadcrumbs")
                or product.get("category_breadcrumb")
            )
            if isinstance(bc, str):
                breadcrumb = bc
            elif isinstance(bc, (tuple, list)):
                breadcrumb = "/".join(bc)

        name = (
            product.get("name")
            or product.get("title")
            or product.get("product_name_raw")
            or product.get("product_name")
            or ""
        )
    else:
        breadcrumb = getattr(getattr(product, "category", None), "breadcrumb", None) or getattr(product, "breadcrumb", "") or ""
        name = getattr(product, "name", None) or getattr(product, "title", None) or ""

    return str(breadcrumb).strip(), str(name).strip()


def evaluate_laptop_eligibility(product: SearchProduct | dict[str, Any] | Any) -> EligibilityResult:
    """Classify physical laptops using category breadcrumb as primary criteria,

    backed by a secondary negative title guard.
    """
    breadcrumb, name = _extract_breadcrumb_and_name(product)
    breadcrumb_lower = breadcrumb.lower()
    name_lower = name.lower()

    if not breadcrumb_lower:
        return EligibilityResult(
            accepted=False,
            reason="Breadcrumb is missing or empty",
        )

    # Primary check: Category breadcrumb whitelist
    is_allowed_prefix = any(breadcrumb_lower.startswith(prefix) for prefix in ALLOWED_BREADCRUMB_PREFIXES)
    is_allowed_exact = breadcrumb_lower in ALLOWED_BREADCRUMB_EXACT

    if not (is_allowed_prefix or is_allowed_exact):
        return EligibilityResult(
            accepted=False,
            reason=f"Breadcrumb '{breadcrumb}' is not an allowed laptop category",
        )

    # Secondary check: Negative title guard for obvious accessories/parts
    for keyword in sorted(NEGATIVE_TITLE_KEYWORDS):
        if keyword in name_lower:
            return EligibilityResult(
                accepted=False,
                reason=f"Product title contains accessory keyword '{keyword}'",
            )

    return EligibilityResult(
        accepted=True,
        reason="Eligible laptop category and title",
    )


def is_laptop_candidate(title: str, breadcrumbs: tuple[str, ...] | str = ()) -> bool:
    """Backward-compatibility wrapper for legacy callers."""
    if isinstance(breadcrumbs, (tuple, list)):
        bc_str = "/".join(breadcrumbs)
    else:
        bc_str = str(breadcrumbs)

    res = evaluate_laptop_eligibility({"name": title, "breadcrumb": bc_str})
    if res.accepted:
        return True

    # Secondary title negative guard
    title_lower = title.lower()
    if any(kw in title_lower for kw in NEGATIVE_TITLE_KEYWORDS):
        return False

    # Fallback for legacy breadcrumb tuples (e.g. ("Komputer", "Laptop"))
    if isinstance(breadcrumbs, (tuple, list)):
        has_laptop_crumb = any("laptop" in c.lower() or "notebook" in c.lower() for c in breadcrumbs)
        if has_laptop_crumb:
            return True

    # Fallback for title-based check when breadcrumb is missing or non-standard
    return any(term in title_lower for term in _POSITIVE_TITLE_TERMS)
