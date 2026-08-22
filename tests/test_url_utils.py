
import pytest

from laptop_market_scraper.url_utils import (
    canonicalize_product_url,
    is_tokopedia_product_url,
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

