"""Tests for the listing discovery parser and Tokopedia embedded state fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from scrapling.parser import Adaptor

from laptop_market_scraper.parsers.listing import (
    _is_product_link,
    extract_next_page,
    extract_product_links,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def inventory_scripts(response_or_html: Adaptor | str) -> dict[str, Any]:
    """Analyze script tags, types, IDs, and presence of hydration markers."""
    if isinstance(response_or_html, str):
        page = Adaptor(response_or_html)
        raw_html = response_or_html
    else:
        page = response_or_html
        raw_html = getattr(page, "body", None) or getattr(page, "html_content", "") or str(page)

    scripts = page.css("script")
    types = [s.attrib.get("type", "text/javascript") for s in scripts]
    ids = [s.attrib.get("id") for s in scripts if "id" in s.attrib]
    script_texts = [s.text or "" for s in scripts]

    has_next_data = (
        any(s.attrib.get("id") == "__NEXT_DATA__" for s in scripts)
        or "__NEXT_DATA__" in str(raw_html)
    )
    has_initial_state = any(
        "window.__INITIAL_STATE__" in st or "__INITIAL_STATE__" in st for st in script_texts
    ) or "__INITIAL_STATE__" in str(raw_html)
    has_next_flight = (
        any("self.__next_f" in st for st in script_texts) or "self.__next_f" in str(raw_html)
    )

    return {
        "total_scripts": len(scripts),
        "types": types,
        "ids": ids,
        "has_next_data": has_next_data,
        "has_initial_state": has_initial_state,
        "has_next_flight": has_next_flight,
    }


@pytest.fixture
def listing_response():
    html = (FIXTURE_DIR / "listing_page.html").read_text(encoding="utf-8")
    page = Adaptor(html, url="https://www.tokopedia.com/search?st=product&q=laptop")
    return page


@pytest.fixture
def tokopedia_search_state_response():
    html = (FIXTURE_DIR / "tokopedia_search_state.html").read_text(encoding="utf-8")
    page = Adaptor(html, url="https://www.tokopedia.com/search?st=product&q=laptop")
    return page


@pytest.fixture
def tokopedia_search_raw_response():
    html = (FIXTURE_DIR / "tokopedia_search_raw.html").read_text(encoding="utf-8")
    page = Adaptor(html, url="https://www.tokopedia.com/search?st=product&q=laptop&page=2")
    return page


# ---------------------------------------------------------------------------
# Legacy DOM Parser Tests (listing_page.html)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Task 1: Script Inventory & Carrier Identification Tests
# ---------------------------------------------------------------------------


def test_tokopedia_search_state_fixture_inventory(tokopedia_search_state_response):
    """Inventory scripts, verify __NEXT_DATA__ marker, and inspect carrier payload."""
    inv = inventory_scripts(tokopedia_search_state_response)

    assert inv["total_scripts"] >= 2
    assert "application/json" in inv["types"]
    assert "__NEXT_DATA__" in inv["ids"]
    assert inv["has_next_data"] is True
    assert inv["has_next_flight"] is False

    # Inspect Next.js __NEXT_DATA__ payload
    next_data_scripts = tokopedia_search_state_response.css('script[id="__NEXT_DATA__"]')
    assert len(next_data_scripts) == 1
    raw_json = next_data_scripts[0].text
    payload = json.loads(raw_json)

    # Carrier navigation: props -> pageProps -> initialState -> searchProduct -> data
    carrier = payload["props"]["pageProps"]["initialState"]["searchProduct"]["data"]
    products = carrier["products"]
    pagination = carrier["pagination"]

    assert len(products) == 3
    # Check exact product record attributes
    assert products[0]["id"] == "11101"
    assert "ASUS Vivobook" in products[0]["name"]
    assert products[0]["url"].startswith("https://www.tokopedia.com/asus-official/")
    assert products[0]["priceInt"] == 6499000
    assert products[0]["ratingAverage"] == "4.9"
    assert products[0]["shop"]["name"] == "ASUS Official Store"

    # Check pagination metadata
    assert pagination["currentPage"] == 1
    assert pagination["totalPages"] == 50
    assert pagination["hasNextPage"] is True
    assert pagination["totalData"] == 1200
    assert pagination["pageSize"] == 24


def test_tokopedia_search_raw_fixture_inventory(tokopedia_search_raw_response):
    """Inventory scripts and decode window.__INITIAL_STATE__ carrier payload."""
    inv = inventory_scripts(tokopedia_search_raw_response)

    assert inv["total_scripts"] >= 2
    assert inv["has_initial_state"] is True

    # Decode window.__INITIAL_STATE__ using raw_decode
    html_text = (FIXTURE_DIR / "tokopedia_search_raw.html").read_text(encoding="utf-8")
    marker = "window.__INITIAL_STATE__"
    marker_pos = html_text.find(marker)
    assert marker_pos != -1

    eq_pos = html_text.find("=", marker_pos)
    start_pos = html_text.find("{", eq_pos)
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(html_text, start_pos)

    # Carrier navigation: displaySearchQuery -> data
    carrier = payload["displaySearchQuery"]["data"]
    products = carrier["products"]
    pagination = carrier["pagination"]

    assert len(products) == 2
    assert products[0]["id"] == "22201"
    assert "HP Pavilion" in products[0]["title"]
    assert products[0]["url"].startswith("https://www.tokopedia.com/hp-indonesia/")
    assert products[0]["priceInt"] == 10999000

    assert pagination["currentPage"] == 2
    assert pagination["totalPages"] == 20
    assert pagination["hasNextPage"] is True
    assert pagination["totalData"] == 480


# ---------------------------------------------------------------------------
# Task 1: Regression Tests Demonstrating DOM-Only Limitation on CSR State
# ---------------------------------------------------------------------------


def test_dom_parser_extracts_no_links_from_state_only_fixture(tokopedia_search_state_response):
    """Evidence test: DOM-only extract_product_links returns empty list on CSR HTML."""
    urls = extract_product_links(tokopedia_search_state_response)
    # The fixture contains 0 <a> tags matching product path patterns in DOM
    assert urls == []


def test_dom_parser_extracts_no_next_page_from_state_only_fixture(tokopedia_search_state_response):
    """Evidence test: DOM-only extract_next_page returns None on CSR HTML."""
    next_url = extract_next_page(tokopedia_search_state_response)
    # No <a rel="next"> exists in DOM
    assert next_url is None


def test_captured_tokopedia_state_contains_valid_product_listings(tokopedia_search_state_response):
    """Validate that product URLs inside the captured state are canonical Tokopedia URLs."""
    next_data = json.loads(tokopedia_search_state_response.css('script[id="__NEXT_DATA__"]')[0].text)
    products = next_data["props"]["pageProps"]["initialState"]["searchProduct"]["data"]["products"]

    for prod in products:
        url = prod["url"]
        assert _is_product_link(url, "tokopedia.com")
        assert url.startswith("https://www.tokopedia.com/")
