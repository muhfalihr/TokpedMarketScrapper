"""Product URL discovery from listing/search pages."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse


_TOKOPEDIA_DOMAIN = "tokopedia.com"

_NON_PRODUCT_PATH_PREFIXES = (
    "/search",
    "/p/",
    "/hot/",
    "/discovery/",
    "/find/",
)


def _is_product_link(url: str, base_domain: str) -> bool:
    """Return True if *url* looks like a product detail page on the same domain."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if base_domain not in host:
        return False

    path = parsed.path
    if not path or path == "/":
        return False

    for prefix in _NON_PRODUCT_PATH_PREFIXES:
        if path.startswith(prefix):
            return False

    # Product URLs on Tokopedia have at least two path segments: /<shop>/<product>
    segments = [s for s in path.split("/") if s]
    return len(segments) >= 2


def extract_product_links(response) -> list[str]:
    """Extract unique, same-domain product URLs from a listing page response.

    *response* must be a Scrapling Adaptor or similar object exposing
    ``css()`` for selector queries.  Each element must support
    ``attrib["href"]``.

    Returns deduplicated URLs in discovery order.
    """
    seen: set[str] = set()
    result: list[str] = []

    base_url = str(response.url) if hasattr(response, "url") else ""
    base_domain = _TOKOPEDIA_DOMAIN

    for anchor in response.css("a[href]"):
        href = anchor.attrib.get("href", "")
        if not href:
            continue

        absolute = urljoin(base_url, href)
        # Strip fragment
        absolute = absolute.split("#")[0]

        if not _is_product_link(absolute, base_domain):
            continue

        if absolute not in seen:
            seen.add(absolute)
            result.append(absolute)

    return result


def extract_next_page(response) -> str | None:
    """Find the next-page link from a listing page response.

    Looks for ``<a rel="next">`` or common pagination patterns.
    Returns an absolute URL or None.
    """
    base_url = str(response.url) if hasattr(response, "url") else ""

    for anchor in response.css('a[rel="next"]'):
        href = anchor.attrib.get("href", "")
        if href:
            return urljoin(base_url, href)

    return None
