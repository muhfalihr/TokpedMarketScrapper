"""URL canonicalization and listing identity."""

from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset({
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "src",
    "extParam",
    "ref",
})


def canonicalize_product_url(url: str) -> str:
    """Strip tracking parameters and fragment from a Tokopedia product URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)

    filtered = {
        k: v for k, v in sorted(qs.items()) if k not in _TRACKING_PARAMS
    }

    clean = parsed._replace(
        query=urlencode(filtered, doseq=True) if filtered else "",
        fragment="",
    )
    return urlunparse(clean)


def make_listing_key(product_id: str | None, canonical_url: str) -> str:
    """Produce a deterministic identity string for a product listing.

    Prefers product_id when available; falls back to a hash of the
    canonical URL.
    """
    if product_id:
        return f"pid:{product_id}"
    return f"url:{sha256(canonical_url.encode()).hexdigest()[:16]}"
