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
