"""Tests for the listing discovery parser, unified state extraction, and Tokopedia fixtures."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from scrapling.parser import Adaptor

from laptop_market_scraper.parsers.listing import (
    ListingDiagnostics,
    ListingPageData,
    _extract_dom_next_page,
    _extract_dom_product_links,
    _is_product_link,
    extract_next_page,
    extract_product_links,
    parse_listing_page,
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
    """Evidence test: DOM-only _extract_dom_product_links returns empty list on CSR HTML."""
    urls = _extract_dom_product_links(tokopedia_search_state_response)
    # The fixture contains 0 <a> tags matching product path patterns in DOM
    assert urls == []


def test_dom_parser_extracts_no_next_page_from_state_only_fixture(tokopedia_search_state_response):
    """Evidence test: DOM-only _extract_dom_next_page returns None on CSR HTML."""
    next_url = _extract_dom_next_page(tokopedia_search_state_response)
    # No <a rel="next"> exists in DOM
    assert next_url is None


def test_captured_tokopedia_state_contains_valid_product_listings(tokopedia_search_state_response):
    """Validate that product URLs inside the captured state are canonical Tokopedia URLs."""
    next_data = json.loads(
        tokopedia_search_state_response.css('script[id="__NEXT_DATA__"]')[0].text
    )
    products = next_data["props"]["pageProps"]["initialState"]["searchProduct"]["data"]["products"]

    for prod in products:
        url = prod["url"]
        assert _is_product_link(url, "tokopedia.com")
        assert url.startswith("https://www.tokopedia.com/")


# ---------------------------------------------------------------------------
# Task 5: Unified Listing Parser Tests
# ---------------------------------------------------------------------------


def test_listing_diagnostics_dataclass_defaults():
    """Verify ListingDiagnostics field defaults and mutability."""
    diag = ListingDiagnostics()
    assert diag.scripts_scanned == 0
    assert diag.state_candidates_found == 0
    assert diag.json_decode_errors == 0
    assert diag.next_f_detected is False
    assert diag.product_records_seen == 0
    assert diag.product_urls_accepted == 0
    assert diag.product_urls_rejected == 0
    assert diag.dom_fallback_used is False


def test_listing_page_data_dataclass_immutability():
    """Verify ListingPageData is frozen."""
    data = ListingPageData(
        product_urls=("https://www.tokopedia.com/asus/laptop-1",),
        current_page=1,
        next_page=2,
        has_next_page=True,
        total_products=100,
        state_source="__NEXT_DATA__",
        dom_fallback_used=False,
        diagnostics=ListingDiagnostics(),
    )
    assert data.current_page == 1
    assert data.next_page == 2
    assert data.has_next_page is True
    assert data.total_products == 100
    assert data.state_source == "__NEXT_DATA__"
    assert data.dom_fallback_used is False

    with pytest.raises(FrozenInstanceError):
        data.current_page = 2  # type: ignore[misc]


def test_parse_listing_page_next_data_fixture(tokopedia_search_state_response):
    """Verify parse_listing_page on __NEXT_DATA__ state fixture."""
    data = parse_listing_page(tokopedia_search_state_response)

    assert isinstance(data, ListingPageData)
    assert data.dom_fallback_used is False
    assert data.state_source == "__NEXT_DATA__"
    assert len(data.product_urls) == 3
    assert data.current_page == 1
    assert data.next_page == 2
    assert data.has_next_page is True
    assert data.total_products == 1200

    # Diagnostic checks
    assert data.diagnostics.scripts_scanned >= 2
    assert data.diagnostics.state_candidates_found >= 1
    assert data.diagnostics.next_f_detected is False
    assert data.diagnostics.product_records_seen == 3
    assert data.diagnostics.product_urls_accepted == 3
    assert data.diagnostics.product_urls_rejected == 0
    assert data.diagnostics.dom_fallback_used is False


def test_parse_listing_page_raw_initial_state_fixture(tokopedia_search_raw_response):
    """Verify parse_listing_page on window.__INITIAL_STATE__ fixture."""
    data = parse_listing_page(tokopedia_search_raw_response)

    assert isinstance(data, ListingPageData)
    assert data.dom_fallback_used is False
    assert data.state_source == "window.__INITIAL_STATE__"
    assert len(data.product_urls) == 2
    assert data.current_page == 2
    assert data.next_page == 3
    assert data.has_next_page is True
    assert data.total_products == 480

    # Diagnostic checks
    assert data.diagnostics.state_candidates_found >= 1
    assert data.diagnostics.product_records_seen == 2
    assert data.diagnostics.product_urls_accepted == 2
    assert data.diagnostics.product_urls_rejected == 0
    assert data.diagnostics.dom_fallback_used is False


def test_parse_listing_page_dom_only_fixture(listing_response):
    """Verify parse_listing_page falls back to DOM when no state scripts exist."""
    data = parse_listing_page(listing_response)

    assert isinstance(data, ListingPageData)
    assert data.dom_fallback_used is True
    assert data.state_source is None
    assert len(data.product_urls) == 2
    assert data.product_urls == (
        "https://www.tokopedia.com/shop/asus-vivobook",
        "https://www.tokopedia.com/shop/lenovo-loq",
    )
    assert data.has_next_page is True
    assert data.next_page == 2

    # Diagnostics
    assert data.diagnostics.dom_fallback_used is True
    assert data.diagnostics.state_candidates_found == 0
    assert data.diagnostics.product_urls_accepted == 2


def test_parse_listing_page_empty_fixture():
    """Verify parse_listing_page handles empty page without crash."""
    html = "<html><body><div>No items found</div></body></html>"
    data = parse_listing_page(html)

    assert isinstance(data, ListingPageData)
    assert data.dom_fallback_used is True
    assert data.product_urls == ()
    assert data.current_page is None
    assert data.next_page is None
    assert data.has_next_page is None
    assert data.total_products is None
    assert data.diagnostics.scripts_scanned == 0
    assert data.diagnostics.state_candidates_found == 0
    assert data.diagnostics.product_records_seen == 0
    assert data.diagnostics.product_urls_accepted == 0


def test_parse_listing_page_malformed_state_falls_back_to_dom():
    """Verify malformed JSON/JS syntax logs decode error and falls back to DOM."""
    html = """
    <html>
      <head>
        <script type="application/json">{"broken": json,</script>
        <script>window.__INITIAL_STATE__ = {invalid syntax;</script>
      </head>
      <body>
        <a href="https://www.tokopedia.com/shop/lenovo-ideapad">Lenovo IdeaPad</a>
        <a href="https://www.tokopedia.com/search?page=2" rel="next">Next</a>
      </body>
    </html>
    """
    data = parse_listing_page(html)

    assert data.dom_fallback_used is True
    assert data.product_urls == ("https://www.tokopedia.com/shop/lenovo-ideapad",)
    assert data.has_next_page is True
    assert data.next_page == 2
    assert data.diagnostics.scripts_scanned == 2
    assert data.diagnostics.json_decode_errors >= 2
    assert data.diagnostics.dom_fallback_used is True
    assert data.diagnostics.product_urls_accepted == 1


def test_parse_listing_page_generic_recovery():
    """Verify parse_listing_page uses generic recovery when known adapter schema shifts."""
    html = """
    <html>
      <head>
        <script type="application/json">
        {
          "alteredCatalog": {
            "results": [
              {"title": "Dell XPS 15", "productUrl": "https://www.tokopedia.com/dell/dell-xps-15", "price": "22000000"}
            ],
            "pageNumber": 1,
            "pageCount": 5,
            "hasNext": true
          }
        }
        </script>
      </head>
      <body></body>
    </html>
    """
    data = parse_listing_page(html)

    assert data.dom_fallback_used is False
    assert data.product_urls == ("https://www.tokopedia.com/dell/dell-xps-15",)
    assert data.current_page == 1
    assert data.next_page == 2
    assert data.has_next_page is True
    assert data.diagnostics.dom_fallback_used is False
    assert data.diagnostics.product_urls_accepted == 1


def test_parse_listing_page_next_flight_marker_detected():
    """Verify Next.js Flight marker is recorded in diagnostics."""
    html = """
    <html>
      <head>
        <script>self.__next_f.push([1, "some flight chunk"]);</script>
      </head>
      <body>
        <a href="https://www.tokopedia.com/shop/acer-aspire">Acer Aspire</a>
      </body>
    </html>
    """
    data = parse_listing_page(html)

    assert data.diagnostics.next_f_detected is True
    assert data.dom_fallback_used is True
    assert data.product_urls == ("https://www.tokopedia.com/shop/acer-aspire",)


def test_extract_product_links_unified_delegation(
    tokopedia_search_state_response, tokopedia_search_raw_response, listing_response
):
    """Verify extract_product_links delegates to parse_listing_page for state & DOM."""
    urls_state = extract_product_links(tokopedia_search_state_response)
    assert len(urls_state) == 3
    assert urls_state[0].startswith("https://www.tokopedia.com/asus-official/")

    urls_raw = extract_product_links(tokopedia_search_raw_response)
    assert len(urls_raw) == 2
    assert urls_raw[0].startswith("https://www.tokopedia.com/hp-indonesia/")

    urls_dom = extract_product_links(listing_response)
    assert len(urls_dom) == 2


def test_extract_next_page_unified_delegation(
    tokopedia_search_state_response, tokopedia_search_raw_response, listing_response
):
    """Verify extract_next_page extracts next page link for state & DOM."""
    next_state = extract_next_page(tokopedia_search_state_response)
    assert next_state is not None
    assert "page=2" in next_state

    next_raw = extract_next_page(tokopedia_search_raw_response)
    assert next_raw is not None
    assert "page=3" in next_raw

    next_dom = extract_next_page(listing_response)
    assert next_dom is not None
    assert "page=2" in next_dom
