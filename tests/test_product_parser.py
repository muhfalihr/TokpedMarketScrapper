"""Tests for the product detail parser."""

from pathlib import Path

import pytest
from scrapling.parser import Adaptor

from tokped_market_scrapper.models import ListingSeed
from tokped_market_scrapper.parsers.product import parse_product

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def listing_seed():
    return ListingSeed(
        product_url="https://www.tokopedia.com/shop/product",
        source_type="search",
        source_query="laptop",
        source_url="https://www.tokopedia.com/search?q=laptop",
        source_page=1,
    )


@pytest.fixture
def product_response():
    html = (FIXTURE_DIR / "product_jsonld.html").read_text(encoding="utf-8")
    return Adaptor(html, url="https://www.tokopedia.com/shop/asus-vivobook")


@pytest.fixture
def dom_response():
    html = (FIXTURE_DIR / "product_dom_fallback.html").read_text(encoding="utf-8")
    return Adaptor(html, url="https://www.tokopedia.com/shop/lenovo-loq")


def test_product_parser_prefers_structured_data(product_response, listing_seed):
    item = parse_product(product_response, listing_seed, "run-1")

    assert item.product_name_raw == "ASUS Vivobook 14"
    assert item.price_raw == "12499000"
    assert item.rating_raw == "4.9"
    assert item.review_count_raw == "321"
    assert item.brand == "ASUS"


def test_product_parser_can_recover_public_text_fields(dom_response, listing_seed):
    item = parse_product(dom_response, listing_seed, "run-1")

    assert item.product_name_raw == "Lenovo LOQ Gaming Laptop"
    assert item.price_raw == "Rp15.999.000"
    assert item.sold_count_raw == "1,2rb+ terjual"
