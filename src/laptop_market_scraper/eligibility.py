"""Laptop-vs-accessory classification rules."""


_POSITIVE_TERMS = frozenset({
    "laptop",
    "notebook",
    "ultrabook",
    "chromebook",
    "macbook",
})

_ACCESSORY_PHRASES = (
    "tas laptop",
    "sleeve laptop",
    "charger laptop",
    "adaptor laptop",
    "adapter laptop",
    "cooling pad",
    "stand laptop",
    "baterai laptop",
    "battery laptop",
    "screen protector",
    "lcd laptop",
    "keyboard laptop",
    "mouse laptop",
    "casing laptop",
)

_LAPTOP_BREADCRUMBS = frozenset({"laptop", "notebook"})


def is_laptop_candidate(title: str, breadcrumbs: tuple[str, ...]) -> bool:
    """Determine whether a product listing is likely an actual laptop.

    Breadcrumb category containing 'laptop' or 'notebook' has priority
    over title heuristic.
    """
    # Breadcrumb check has priority
    for crumb in breadcrumbs:
        crumb_lower = crumb.lower()
        if any(term in crumb_lower for term in _LAPTOP_BREADCRUMBS):
            return True

    title_lower = title.lower()

    # Check accessory exclusion phrases first
    for phrase in _ACCESSORY_PHRASES:
        if phrase in title_lower:
            return False

    # Check for positive laptop terms
    for term in _POSITIVE_TERMS:
        if term in title_lower:
            return True

    return False
