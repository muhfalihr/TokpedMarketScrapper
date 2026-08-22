import pytest

from laptop_market_scraper.url_utils import canonicalize_product_url, make_listing_key


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
