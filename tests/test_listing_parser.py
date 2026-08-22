"""Tests for the listing discovery parser."""

from pathlib import Path

import pytest
from scrapling.parser import Adaptor

from laptop_market_scraper.parsers.listing import extract_next_page, extract_product_links

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def listing_response():
    html = (FIXTURE_DIR / "listing_page.html").read_text(encoding="utf-8")
    page = Adaptor(html, url="https://www.tokopedia.com/search?st=product&q=laptop")
    return page


def test_extracts_unique_product_links(listing_response):
    urls = extract_product_links(listing_response)

    assert urls == [
        "https://www.tokopedia.com/shop/asus-vivobook",
        "https://www.tokopedia.com/shop/lenovo-loq",
    ]


def test_extracts_next_page(listing_response):
    next_url = extract_next_page(listing_response)
    assert next_url is not None
    assert next_url.endswith("page=2")
