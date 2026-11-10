from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from typing import Any
from urllib.parse import (
    parse_qs,
    parse_qsl,
    urlencode,
    urlparse,
    urlsplit,
    urlunparse,
    urlunsplit,
)

__all__ = (
    "build_page_url",
    "canonicalize_product_url",
    "is_tokopedia_product_url",
    "listing_fingerprint",
    "make_listing_key",
    "search_page_fingerprint",
)

_TRACKING_PARAMS = frozenset({
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "src",
    "extParam",
    "ref",
})

_RESERVED_ROOT_PATHS = frozenset({
    "about",
    "account",
    "accounts",
    "auth",
    "bantuan",
    "blog",
    "campaign",
    "campaigns",
    "careers",
    "cart",
    "catalog",
    "catalogs",
    "categories",
    "category",
    "checkout",
    "contact",
    "contact-us",
    "deals",
    "discovery",
    "events",
    "feed",
    "find",
    "flight",
    "flights",
    "help",
    "hot",
    "hotel",
    "hotels",
    "kategori",
    "login",
    "mitra",
    "mitra-tokopedia",
    "news",
    "order",
    "order-list",
    "p",
    "payment",
    "people",
    "play",
    "privacy",
    "profile",
    "promo",
    "pulsa",
    "register",
    "search",
    "seller",
    "seller-center",
    "signup",
    "stories",
    "terms",
    "tiket",
    "tokopedia-care",
    "topup",
    "user",
    "users",
})

_STATIC_EXTENSIONS = frozenset({
    ".avi",
    ".bmp",
    ".css",
    ".eot",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".map",
    ".mjs",
    ".mov",
    ".mp3",
    ".mp4",
    ".otf",
    ".pdf",
    ".png",
    ".svg",
    ".tar",
    ".tiff",
    ".ttf",
    ".txt",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xml",
    ".zip",
})

_STATIC_HOSTS = frozenset({
    "accounts.tokopedia.com",
    "api.tokopedia.com",
    "assets.tokopedia.net",
    "ecs7.tokopedia.net",
    "gql.tokopedia.com",
    "images.tokopedia.net",
    "img.tokopedia.net",
    "media.tokopedia.net",
    "scripts.tokopedia.net",
    "seller.tokopedia.com",
    "static.tokopedia.net",
    "ws.tokopedia.com",
})


def is_tokopedia_product_url(url: str) -> bool:
    """Validate if a URL is a valid Tokopedia product listing/detail URL.

    Validation rules:
    1. Must be a valid string with scheme 'http' or 'https'.
    2. Hostname must belong to Tokopedia public domains (e.g. tokopedia.com,
       www.tokopedia.com, ta.tokopedia.com, m.tokopedia.com).
    3. Rejects known static asset hosts and file extensions (e.g., .jpg, .png, .js).
    4. Rejects reserved navigation and non-product routes (search, promo, category,
       cart, login, user profile, etc.).
    5. Requires standard product path structure (at least 2 path segments,
       e.g. /{shop_slug}/{product_slug}), unless hosted on TopAds (ta.tokopedia.com).
    """
    if not isinstance(url, str) or not url.strip():
        return False

    try:
        parsed = urlparse(url.strip())
    except (ValueError, TypeError, AttributeError):
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    # Hostname must be tokopedia.com or a subdomain of tokopedia.com
    if hostname != "tokopedia.com" and not hostname.endswith(".tokopedia.com"):
        return False

    # Reject internal/static asset hosts
    if hostname in _STATIC_HOSTS:
        return False

    # Reject static file extensions
    path = parsed.path.lower()
    for ext in _STATIC_EXTENSIONS:
        if path.endswith(ext):
            return False

    # Extract clean path segments
    segments = [s for s in parsed.path.strip("/").split("/") if s]
    if not segments:
        return False

    # Allow TopAds redirect/click URLs (e.g. ta.tokopedia.com/promo/v1/clicks or ta.tokopedia.com/r)
    if hostname == "ta.tokopedia.com":
        return True

    first_segment = segments[0].lower()
    if first_segment in _RESERVED_ROOT_PATHS:
        return False

    # A valid Tokopedia product URL requires at least shop_slug and product_slug
    return len(segments) >= 2


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


def build_page_url(current_url: str, next_page: int) -> str:
    """Construct a pagination URL for *next_page* while preserving existing query params.

    Uses urllib.parse (urlsplit, parse_qsl, urlencode, urlunsplit) to update or
    insert the `page` query parameter while maintaining query parameter order.
    """
    if not current_url or not isinstance(current_url, str):
        return ""

    parts = urlsplit(current_url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)

    updated = False
    new_query_pairs: list[tuple[str, str]] = []
    for key, val in query_pairs:
        if key == "page":
            new_query_pairs.append((key, str(next_page)))
            updated = True
        else:
            new_query_pairs.append((key, val))

    if not updated:
        new_query_pairs.append(("page", str(next_page)))

    new_query = urlencode(new_query_pairs, doseq=True)
    return urlunsplit(parts._replace(query=new_query))


def listing_fingerprint(product_urls: Sequence[str]) -> str:
    """Generate a deterministic SHA-256 fingerprint for a sequence of product URLs.

    Canonicalizes each non-empty product URL, removes duplicates, sorts them
    lexicographically, and computes the SHA-256 hash of the newline-delimited result.
    """
    if not product_urls:
        return sha256(b"").hexdigest()

    canonical_set = {
        canonicalize_product_url(u)
        for u in product_urls
        if isinstance(u, str) and u.strip()
    }
    if not canonical_set:
        return sha256(b"").hexdigest()

    sorted_urls = sorted(canonical_set)
    payload = "\n".join(sorted_urls).encode("utf-8")
    return sha256(payload).hexdigest()


def search_page_fingerprint(products: Sequence[Any]) -> str:
    """Generate a deterministic SHA-256 fingerprint for a sequence of search products or product IDs.

    Hashes ordered product IDs joined by commas.
    """
    if not products:
        return sha256(b"").hexdigest()

    ids: list[str] = []
    for item in products:
        if hasattr(item, "product_id"):
            ids.append(str(item.product_id))
        elif isinstance(item, dict) and "product_id" in item:
            ids.append(str(item["product_id"]))
        elif isinstance(item, dict) and "id" in item:
            ids.append(str(item["id"]))
        elif isinstance(item, str):
            ids.append(item)

    payload = ",".join(ids).encode("utf-8")
    return sha256(payload).hexdigest()


