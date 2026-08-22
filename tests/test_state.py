"""Tests for embedded state candidate discovery and extraction."""

from __future__ import annotations

from pathlib import Path

import pytest
from scrapling.parser import Adaptor

from laptop_market_scraper.parsers.state import (
    StateCandidate,
    StateListingResult,
    TokopediaListingStateAdapter,
    decode_json_assignment,
    detect_flight_marker,
    extract_state_candidates,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tokopedia_search_state_html() -> str:
    return (FIXTURE_DIR / "tokopedia_search_state.html").read_text(encoding="utf-8")


@pytest.fixture
def tokopedia_search_raw_html() -> str:
    return (FIXTURE_DIR / "tokopedia_search_raw.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Required Brief Tests
# ---------------------------------------------------------------------------


def test_extracts_application_json():
    """Verify standard <script type="application/json"> is parsed."""
    html = """
    <html>
      <head>
        <script type="application/json">{"config": {"theme": "dark", "version": 2}}</script>
      </head>
      <body></body>
    </html>
    """
    candidates = extract_state_candidates(html)
    assert len(candidates) == 1
    assert candidates[0].source == "application/json"
    assert candidates[0].payload == {"config": {"theme": "dark", "version": 2}}
    assert candidates[0].script_index == 0


def test_extracts_next_data_json():
    """Verify Next.js <script id="__NEXT_DATA__"> is extracted with '__NEXT_DATA__' source."""
    html = """
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
          {"props": {"pageProps": {"products": [{"id": 1, "name": "Laptop"}]}}}
        </script>
      </head>
      <body></body>
    </html>
    """
    candidates = extract_state_candidates(html)
    assert len(candidates) == 1
    assert candidates[0].source == "__NEXT_DATA__"
    assert candidates[0].payload == {
        "props": {"pageProps": {"products": [{"id": 1, "name": "Laptop"}]}}
    }
    assert candidates[0].script_index == 0


def test_extracts_window_initial_state_with_raw_decode():
    """Verify JS global window assignment is decoded via raw_decode handling tricky characters."""
    html = """
    <html>
      <head>
        <script>
          window.__INITIAL_STATE__ = {
            "query": "laptop",
            "escapedBraces": "foo }; bar",
            "nested": {"count": 42}
          };
          var otherCode = true;
        </script>
      </head>
    </html>
    """
    candidates = extract_state_candidates(html)
    assert len(candidates) == 1
    assert candidates[0].source == "window.__INITIAL_STATE__"
    assert candidates[0].payload == {
        "query": "laptop",
        "escapedBraces": "foo }; bar",
        "nested": {"count": 42},
    }
    assert candidates[0].script_index == 0


def test_ignores_malformed_json_without_crashing():
    """Verify malformed JSON scripts or broken JS assignments are safely skipped."""
    html = """
    <html>
      <head>
        <script type="application/json">{"incomplete": </script>
        <script>window.__INITIAL_STATE__ = {broken syntax;</script>
        <script>window.__PRELOADED_STATE__ = ;</script>
        <script id="__NEXT_DATA__" type="application/json"></script>
        <script type="text/javascript">var x = 123;</script>
      </head>
    </html>
    """
    candidates = extract_state_candidates(html)
    assert candidates == []


# ---------------------------------------------------------------------------
# Fixture Validation Tests
# ---------------------------------------------------------------------------


def test_extracts_candidates_from_tokopedia_search_state_fixture(tokopedia_search_state_html):
    """Verify extraction against real Next.js fixture tokopedia_search_state.html."""
    candidates = extract_state_candidates(tokopedia_search_state_html)
    assert len(candidates) >= 1

    next_data_candidate = next((c for c in candidates if c.source == "__NEXT_DATA__"), None)
    assert next_data_candidate is not None
    payload = next_data_candidate.payload
    assert isinstance(payload, dict)
    assert "props" in payload
    assert "pageProps" in payload["props"]
    products = payload["props"]["pageProps"]["initialState"]["searchProduct"]["data"]["products"]
    assert len(products) == 3
    assert products[0]["id"] == "11101"


def test_extracts_candidates_from_tokopedia_search_raw_fixture(tokopedia_search_raw_html):
    """Verify extraction against real window.__INITIAL_STATE__ fixture tokopedia_search_raw.html."""
    candidates = extract_state_candidates(tokopedia_search_raw_html)
    assert len(candidates) >= 1

    initial_state_candidate = next(
        (c for c in candidates if c.source == "window.__INITIAL_STATE__"), None
    )
    assert initial_state_candidate is not None
    payload = initial_state_candidate.payload
    assert isinstance(payload, dict)
    assert "displaySearchQuery" in payload
    products = payload["displaySearchQuery"]["data"]["products"]
    assert len(products) == 2
    assert products[0]["id"] == "22201"


# ---------------------------------------------------------------------------
# Next.js Flight and Helper Tests
# ---------------------------------------------------------------------------


def test_skips_next_flight_marker_without_blind_decoding():
    """Verify Next.js Flight RSC stream chunks are skipped without crashing."""
    html = """
    <html>
      <head>
        <script>
          (self.__next_f=self.__next_f||[]).push([0]);
          self.__next_f.push([1, "1:I[\"foo\"]\n2:[\"$\",\"$L1\",null,{\"items\":[]}]\n"]);
        </script>
      </head>
    </html>
    """
    candidates = extract_state_candidates(html)
    assert candidates == []


def test_detect_flight_marker():
    """Verify detect_flight_marker accurately identifies RSC Flight streams."""
    flight_html = '<script>self.__next_f.push([1, "chunk"]);</script>'
    normal_html = '<script id="__NEXT_DATA__">{"props": {}}</script>'

    assert detect_flight_marker(flight_html) is True
    assert detect_flight_marker(Adaptor(flight_html)) is True
    assert detect_flight_marker(normal_html) is False
    assert detect_flight_marker(Adaptor(normal_html)) is False


# ---------------------------------------------------------------------------
# decode_json_assignment Unit Tests
# ---------------------------------------------------------------------------


def test_decode_json_assignment_handles_variations():
    """Verify decode_json_assignment handles formatting whitespace and array payloads."""
    # Extra spacing and newlines
    script1 = '  window.__PRELOADED_STATE__   =\n\t  {"user": "alice", "items": [1, 2, 3]};  '
    res1 = decode_json_assignment(script1, "window.__PRELOADED_STATE__")
    assert res1 == {"user": "alice", "items": [1, 2, 3]}

    # Array assignment
    script2 = "window.__APOLLO_STATE__=[{\"id\": \"item-1\"}, {\"id\": \"item-2\"}];"
    res2 = decode_json_assignment(script2, "window.__APOLLO_STATE__")
    assert res2 == [{"id": "item-1"}, {"id": "item-2"}]

    # Marker absent
    assert decode_json_assignment("var a = 1;", "window.__INITIAL_STATE__") is None

    # Missing assignment operator
    assert decode_json_assignment("window.__INITIAL_STATE__", "window.__INITIAL_STATE__") is None

    # Non-whitespace between marker and =
    assert decode_json_assignment("window.__INITIAL_STATE__.foo = 1;", "window.__INITIAL_STATE__") is None


def test_extract_state_candidates_multiple_scripts_ordering():
    """Verify multiple state candidates are extracted preserving script tag order."""
    html = """
    <html>
      <head>
        <script type="application/json">{"index": 0}</script>
        <script>var ignored = 1;</script>
        <script>window.__PRELOADED_STATE__ = {"index": 2};</script>
        <script id="__NEXT_DATA__" type="application/json">{"index": 3}</script>
      </head>
    </html>
    """
    candidates = extract_state_candidates(html)
    assert len(candidates) == 3
    assert candidates[0] == StateCandidate(
        source="application/json", payload={"index": 0}, script_index=0
    )
    assert candidates[1] == StateCandidate(
        source="window.__PRELOADED_STATE__", payload={"index": 2}, script_index=2
    )
    assert candidates[2] == StateCandidate(
        source="__NEXT_DATA__", payload={"index": 3}, script_index=3
    )


def test_extract_state_candidates_empty_and_non_script_inputs():
    """Verify empty and non-script HTML inputs return empty candidate lists."""
    assert extract_state_candidates("") == []
    assert extract_state_candidates("<html><body><h1>Hello World</h1></body></html>") == []
    assert extract_state_candidates(Adaptor("<div>No scripts here</div>")) == []


# ---------------------------------------------------------------------------
# Task 3: TokopediaListingStateAdapter Unit Tests
# ---------------------------------------------------------------------------


def test_tokopedia_adapter_supports_next_data_candidate(tokopedia_search_state_html):
    """Verify adapter supports __NEXT_DATA__ candidate from Next.js listing fixture."""
    candidates = extract_state_candidates(tokopedia_search_state_html)
    next_data_candidate = next(c for c in candidates if c.source == "__NEXT_DATA__")

    adapter = TokopediaListingStateAdapter()
    assert adapter.supports(next_data_candidate) is True
    assert adapter.supports(next_data_candidate.payload) is True


def test_tokopedia_adapter_supports_window_initial_state_candidate(tokopedia_search_raw_html):
    """Verify adapter supports window.__INITIAL_STATE__ candidate from raw fixture."""
    candidates = extract_state_candidates(tokopedia_search_raw_html)
    initial_state_candidate = next(
        c for c in candidates if c.source == "window.__INITIAL_STATE__"
    )

    adapter = TokopediaListingStateAdapter()
    assert adapter.supports(initial_state_candidate) is True
    assert adapter.supports(initial_state_candidate.payload) is True


def test_tokopedia_adapter_extracts_search_state_fixture(tokopedia_search_state_html):
    """Verify full extraction against tokopedia_search_state.html fixture."""
    candidates = extract_state_candidates(tokopedia_search_state_html)
    next_data_candidate = next(c for c in candidates if c.source == "__NEXT_DATA__")

    adapter = TokopediaListingStateAdapter()
    result = adapter.extract(next_data_candidate)

    assert isinstance(result, StateListingResult)
    assert result.source == "tokopedia_adapter"
    assert len(result.product_urls) == 3
    assert result.product_urls == (
        "https://www.tokopedia.com/asus-official/laptop-asus-vivobook-14-a1404za-intel-core-i3-1215u-8gb-512gb-ssd",
        "https://www.tokopedia.com/lenovo-gaming/lenovo-loq-15iax9-intel-core-i5-12450hx-16gb-512gb-rtx-2050",
        "https://www.tokopedia.com/acer-store/acer-aspire-lite-14-al14-31p-intel-n100-8gb-512gb-ssd-win-11",
    )
    assert result.current_page == 1
    assert result.total_pages == 50
    assert result.total_products == 1200
    assert result.has_next_page is True


def test_tokopedia_adapter_extracts_search_raw_fixture(tokopedia_search_raw_html):
    """Verify full extraction against tokopedia_search_raw.html fixture."""
    candidates = extract_state_candidates(tokopedia_search_raw_html)
    initial_state_candidate = next(
        c for c in candidates if c.source == "window.__INITIAL_STATE__"
    )

    adapter = TokopediaListingStateAdapter()
    result = adapter.extract(initial_state_candidate)

    assert isinstance(result, StateListingResult)
    assert result.source == "tokopedia_adapter"
    assert len(result.product_urls) == 2
    assert result.product_urls == (
        "https://www.tokopedia.com/hp-indonesia/hp-pavilion-aero-13-be2001au-ryzen-5-7535u-16gb-512gb",
        "https://www.tokopedia.com/dell-store/dell-inspiron-14-5430-core-i5-1335u-16gb-512gb-ssd",
    )
    assert result.current_page == 2
    assert result.total_pages == 20
    assert result.total_products == 480
    assert result.has_next_page is True


def test_tokopedia_adapter_deduplicates_urls_preserving_order():
    """Verify duplicate URLs and URL fragments are cleaned and deduplicated in discovery order."""
    payload = {
        "searchProduct": {
            "data": {
                "products": [
                    {"url": "https://www.tokopedia.com/shop/item-1#section-1"},
                    {"url": "https://www.tokopedia.com/shop/item-2"},
                    {"url": "https://www.tokopedia.com/shop/item-1#other-fragment"},
                    {"url": "https://www.tokopedia.com/shop/item-3"},
                    {"url": "https://www.tokopedia.com/shop/item-2"},
                ],
                "pagination": {
                    "currentPage": 1,
                    "totalPages": 5,
                    "totalData": 25,
                    "hasNextPage": True,
                },
            }
        }
    }
    adapter = TokopediaListingStateAdapter()
    assert adapter.supports(payload) is True
    result = adapter.extract(payload)

    assert result.product_urls == (
        "https://www.tokopedia.com/shop/item-1",
        "https://www.tokopedia.com/shop/item-2",
        "https://www.tokopedia.com/shop/item-3",
    )
    assert result.current_page == 1
    assert result.total_pages == 5
    assert result.total_products == 25
    assert result.has_next_page is True


def test_tokopedia_adapter_handles_relative_urls():
    """Verify relative product URLs are converted to canonical absolute URLs."""
    payload = {
        "displaySearchQuery": {
            "data": {
                "products": [
                    {"url": "/official-store/laptop-1"},
                    {"url": "/gaming-store/laptop-2"},
                ]
            }
        }
    }
    adapter = TokopediaListingStateAdapter()
    result = adapter.extract(payload)

    assert result.product_urls == (
        "https://www.tokopedia.com/official-store/laptop-1",
        "https://www.tokopedia.com/gaming-store/laptop-2",
    )
    assert result.current_page is None
    assert result.total_pages is None
    assert result.total_products is None
    assert result.has_next_page is None


def test_tokopedia_adapter_empty_products_list():
    """Verify empty product results produce an empty tuple and preserve pagination."""
    payload = {
        "props": {
            "pageProps": {
                "initialState": {
                    "searchProduct": {
                        "data": {
                            "products": [],
                            "pagination": {
                                "currentPage": 1,
                                "totalPages": 0,
                                "totalData": 0,
                                "hasNextPage": False,
                            },
                        }
                    }
                }
            }
        }
    }
    adapter = TokopediaListingStateAdapter()
    assert adapter.supports(payload) is True
    result = adapter.extract(payload)

    assert result.product_urls == ()
    assert result.current_page == 1
    assert result.total_pages == 0
    assert result.total_products == 0
    assert result.has_next_page is False


def test_tokopedia_adapter_rejects_unsupported_payload():
    """Verify unsupported payload is rejected by supports() and raises ValueError in extract()."""
    adapter = TokopediaListingStateAdapter()

    assert adapter.supports(None) is False
    assert adapter.supports(12345) is False
    assert adapter.supports("random text") is False
    assert adapter.supports({"user": {"name": "Alice"}}) is False
    assert adapter.supports(StateCandidate(source="generic", payload={"a": 1}, script_index=0)) is False

    with pytest.raises(ValueError, match="Payload does not match supported Tokopedia listing state structure"):
        adapter.extract({"user": {"name": "Alice"}})


def test_tokopedia_adapter_pagination_type_conversions_and_inferences():
    """Verify string integer conversion and total_pages / has_next_page calculation."""
    payload = {
        "search_product": {
            "data": {
                "products": [
                    {"url": "https://www.tokopedia.com/store/item-1"},
                ],
                "pagination": {
                    "currentPage": "3",
                    "totalData": "90",
                    "pageSize": "30",
                },
            }
        }
    }
    adapter = TokopediaListingStateAdapter()
    result = adapter.extract(payload)

    assert result.current_page == 3
    assert result.total_products == 90
    assert result.total_pages == 3
    assert result.has_next_page is False


def test_state_listing_result_immutability():
    """Verify StateListingResult is an immutable dataclass."""
    res = StateListingResult(
        product_urls=("https://www.tokopedia.com/store/item-1",),
        current_page=1,
        total_pages=10,
        total_products=200,
        has_next_page=True,
    )
    with pytest.raises(AttributeError):
        res.current_page = 2  # type: ignore[misc]

