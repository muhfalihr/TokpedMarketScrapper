
import pytest

from tokped_market_scrapper.url_utils import (
    build_page_url,
    canonicalize_product_url,
    is_tokopedia_product_url,
    listing_fingerprint,
    make_listing_key,
)


def test_removes_tracking_query_and_fragment():
    url = "https://www.tokopedia.com/shop/item?utm_source=x&src=topads#review"
    assert canonicalize_product_url(url) == "https://www.tokopedia.com/shop/item"


def test_listing_key_prefers_product_id():
    first = make_listing_key("12345", "https://example/a")
    second = make_listing_key("12345", "https://example/b")

    assert first == second


def test_listing_key_falls_back_to_canonical_url():
    url_a = "https://www.tokopedia.com/shop/item-a"
    url_b = "https://www.tokopedia.com/shop/item-a"
    url_c = "https://www.tokopedia.com/shop/item-b"

    assert make_listing_key(None, url_a) == make_listing_key(None, url_b)
    assert make_listing_key(None, url_a) != make_listing_key(None, url_c)
    assert make_listing_key("", url_a) == make_listing_key(None, url_b)


def test_canonicalize_preserves_non_tracking_params():
    url = "https://www.tokopedia.com/shop/item?extParam=123&page=2&ref=banner&variant=silver"
    assert canonicalize_product_url(url) == "https://www.tokopedia.com/shop/item?page=2&variant=silver"


def test_canonicalize_handles_clean_urls():
    url = "https://www.tokopedia.com/shop/item"
    assert canonicalize_product_url(url) == "https://www.tokopedia.com/shop/item"


# ---------------------------------------------------------------------------
# is_tokopedia_product_url Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valid_url",
    [
        "https://www.tokopedia.com/asus-official/laptop-asus-vivobook-14",
        "https://tokopedia.com/asus-official/laptop-asus-vivobook-14",
        "http://www.tokopedia.com/lenovo-gaming/lenovo-loq-15iax9",
        "https://m.tokopedia.com/acer-store/acer-aspire-lite-14",
        "https://mobile.tokopedia.com/dell-store/dell-inspiron-14",
        "https://ta.tokopedia.com/promo/v1/clicks?url=https%3A%2F%2Fwww.tokopedia.com%2Fshop%2Fitem",
        "https://ta.tokopedia.com/r?u=https%3A%2F%2Fwww.tokopedia.com%2Fshop%2Fitem",
        "https://www.tokopedia.com/shop/item-slug?extParam=src%3Dsearch&refined=true",
        "https://www.tokopedia.com/shop/item-slug#specification",
    ],
)
def test_is_tokopedia_product_url_accepts_valid_product_urls(valid_url: str):
    """Verify valid product URLs across Tokopedia public domains are accepted."""
    assert is_tokopedia_product_url(valid_url) is True


@pytest.mark.parametrize(
    "noise_url",
    [
        # Non-product navigation and reserved routes
        "https://www.tokopedia.com/search?st=product&q=laptop",
        "https://www.tokopedia.com/find/laptop",
        "https://www.tokopedia.com/p/komputer-laptop",
        "https://www.tokopedia.com/promo",
        "https://www.tokopedia.com/promo/ramadan-sale",
        "https://www.tokopedia.com/discovery/laptop-murah",
        "https://www.tokopedia.com/events/super-sale",
        "https://www.tokopedia.com/campaign/gajian-ekstra",
        "https://www.tokopedia.com/cart",
        "https://www.tokopedia.com/checkout",
        "https://www.tokopedia.com/login",
        "https://www.tokopedia.com/register",
        "https://www.tokopedia.com/user/profile",
        "https://www.tokopedia.com/people/12345",
        "https://www.tokopedia.com/help",
        "https://www.tokopedia.com/bantuan",
        "https://www.tokopedia.com/mitra",
        "https://www.tokopedia.com/pulsa",
        "https://www.tokopedia.com/topup",
        # Single-segment shop/profile URLs (not product)
        "https://www.tokopedia.com/asus-official",
        "https://www.tokopedia.com/lenovo-gaming/",
        "https://www.tokopedia.com/",
        "https://www.tokopedia.com",
        # Static asset hosts and extensions
        "https://images.tokopedia.net/img/cache/700/product-1/laptop.jpg",
        "https://ecs7.tokopedia.net/img/cache/product.png",
        "https://assets.tokopedia.net/assets/main.js",
        "https://static.tokopedia.net/css/style.css",
        "https://www.tokopedia.com/shop/item.jpg",
        "https://www.tokopedia.com/shop/item.png",
        "https://www.tokopedia.com/shop/item.webp",
        "https://www.tokopedia.com/shop/item.svg",
        # Non-tokopedia domains
        "https://shopee.co.id/asus-official/laptop-asus",
        "https://evil-tokopedia.com/asus-official/laptop-asus",
        "https://tokopedia.com.attacker.com/asus-official/laptop-asus",
        "https://www.google.com/url?q=https://tokopedia.com/shop/item",
        # Invalid schemes and protocols
        "ftp://www.tokopedia.com/asus-official/laptop-asus",
        "javascript:alert('xss')",
        "tokopedia://product/12345",
        "data:text/html,<h1>Product</h1>",
    ],
)
def test_is_tokopedia_product_url_rejects_noise_and_non_products(noise_url: str):
    """Verify non-product URLs, static assets, reserved paths, and external domains are rejected."""
    assert is_tokopedia_product_url(noise_url) is False


def test_is_tokopedia_product_url_handles_empty_and_non_string_inputs():
    """Verify empty or non-string inputs safely return False without exceptions."""
    assert is_tokopedia_product_url("") is False
    assert is_tokopedia_product_url("   ") is False
    assert is_tokopedia_product_url(None) is False  # type: ignore[arg-type]
    assert is_tokopedia_product_url(12345) is False  # type: ignore[arg-type]
    assert is_tokopedia_product_url(["https://www.tokopedia.com/a/b"]) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_page_url Unit Tests
# ---------------------------------------------------------------------------


def test_build_page_url_appends_page_when_absent():
    """Verify build_page_url appends page parameter when no query exists."""
    url = "https://www.tokopedia.com/search"
    assert build_page_url(url, 2) == "https://www.tokopedia.com/search?page=2"


def test_build_page_url_preserves_existing_query_params():
    """Verify build_page_url preserves other query params and appends page."""
    url = "https://www.tokopedia.com/search?q=laptop&st=product"
    result = build_page_url(url, 2)
    assert result == "https://www.tokopedia.com/search?q=laptop&st=product&page=2"


def test_build_page_url_updates_existing_page_param():
    """Verify build_page_url updates existing page parameter in-place."""
    url = "https://www.tokopedia.com/search?q=laptop&page=1&st=product"
    result = build_page_url(url, 3)
    assert result == "https://www.tokopedia.com/search?q=laptop&page=3&st=product"


def test_build_page_url_preserves_repeated_and_blank_query_params():
    """Verify build_page_url preserves multi-value parameters and blank values."""
    url = "https://www.tokopedia.com/search?brand=asus&brand=lenovo&filter=&page=2"
    result = build_page_url(url, 4)
    assert result == "https://www.tokopedia.com/search?brand=asus&brand=lenovo&filter=&page=4"


def test_build_page_url_preserves_fragment():
    """Verify build_page_url retains URL fragment if present."""
    url = "https://www.tokopedia.com/search?q=laptop#product-section"
    result = build_page_url(url, 2)
    assert result == "https://www.tokopedia.com/search?q=laptop&page=2#product-section"


def test_build_page_url_handles_empty_and_invalid_inputs():
    """Verify build_page_url handles empty or non-string inputs safely."""
    assert build_page_url("", 2) == ""
    assert build_page_url(None, 2) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# listing_fingerprint Unit Tests
# ---------------------------------------------------------------------------


def test_listing_fingerprint_deterministic_and_order_independent():
    """Verify fingerprint is consistent regardless of product URL sequence order."""
    urls_1 = [
        "https://www.tokopedia.com/shop-a/product-1",
        "https://www.tokopedia.com/shop-b/product-2",
        "https://www.tokopedia.com/shop-c/product-3",
    ]
    urls_2 = [
        "https://www.tokopedia.com/shop-c/product-3",
        "https://www.tokopedia.com/shop-a/product-1",
        "https://www.tokopedia.com/shop-b/product-2",
    ]
    fp_1 = listing_fingerprint(urls_1)
    fp_2 = listing_fingerprint(urls_2)

    assert fp_1 == fp_2
    assert len(fp_1) == 64  # SHA-256 hex length


def test_listing_fingerprint_strips_tracking_params():
    """Verify URLs with tracking parameters produce identical fingerprints to clean URLs."""
    urls_clean = [
        "https://www.tokopedia.com/shop/item-1",
        "https://www.tokopedia.com/shop/item-2",
    ]
    urls_with_tracking = [
        "https://www.tokopedia.com/shop/item-1?utm_source=google&utm_medium=cpc&src=topads#review",
        "https://www.tokopedia.com/shop/item-2?extParam=src%3Dsearch&ref=banner",
    ]
    assert listing_fingerprint(urls_clean) == listing_fingerprint(urls_with_tracking)


def test_listing_fingerprint_handles_empty_and_duplicate_sequences():
    """Verify empty sequences, blank strings, and duplicates are handled deterministically."""
    fp_empty = listing_fingerprint([])
    assert isinstance(fp_empty, str)
    assert len(fp_empty) == 64

    fp_blanks = listing_fingerprint(["", "   "])
    assert fp_blanks == fp_empty

    urls_with_dups = [
        "https://www.tokopedia.com/shop/item-1",
        "https://www.tokopedia.com/shop/item-1",
    ]
    urls_single = ["https://www.tokopedia.com/shop/item-1"]
    assert listing_fingerprint(urls_with_dups) == listing_fingerprint(urls_single)


def test_listing_fingerprint_different_sets_produce_different_hashes():
    """Verify different product sets produce distinct hashes."""
    urls_a = ["https://www.tokopedia.com/shop/asus-zenbook"]
    urls_b = ["https://www.tokopedia.com/shop/lenovo-thinkpad"]
    assert listing_fingerprint(urls_a) != listing_fingerprint(urls_b)


