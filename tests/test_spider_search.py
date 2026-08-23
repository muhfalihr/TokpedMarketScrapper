"""Tests for Tokopedia searchProductV5 GraphQL spider search & safe pagination."""

from unittest.mock import MagicMock, patch

import pytest
from scrapling.parser import Adaptor

from laptop_market_scraper.spiders.tokopedia_laptop import (
    GRAPHQL_URL,
    TokopediaLaptopSpider,
)


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.save.return_value = True
    return store


@pytest.fixture
def spider(mock_store, tmp_path):
    config_yaml = tmp_path / "seeds.yaml"
    config_yaml.write_text(
        """\
search:
  rows: 3
  category_sc: "297"
  sort_code: "23"
  max_pages_per_seed: 5

seeds:
  - query: laptop
    kind: generic
  - query: laptop asus
    kind: brand
    brand_hint: ASUS
"""
    )
    return TokopediaLaptopSpider(
        crawl_run_id="test-search-run",
        store=mock_store,
        seed_config=str(config_yaml),
        contract_path="config/search_product_v5_contract.json",
    )


def make_graphql_response(products_raw, total_data=100, page=1, query="laptop"):
    payload = {
        "data": {
            "searchProductV5": {
                "header": {"totalData": total_data},
                "data": {"products": products_raw},
            }
        }
    }
    response = Adaptor("{}", url=GRAPHQL_URL)
    response.json = lambda: payload
    response.meta = {
        "source_type": "search",
        "source_query": query,
        "seed_kind": "generic",
        "page": page,
        "rows": len(products_raw),
        "category_sc": "297",
        "sort_code": "23",
        "max_pages": 5,
    }
    return response


@pytest.mark.asyncio
async def test_start_requests_yields_graphql_post_requests(spider):
    requests = [r async for r in spider.start_requests()]
    assert len(requests) == 2

    for req in requests:
        assert req._session_kwargs.get("method") == "POST"
        assert req.url == GRAPHQL_URL
        assert req.callback == spider.parse_search_page
        req_json = req._session_kwargs.get("json", {})
        if isinstance(req_json, list):
            req_json = req_json[0]
        assert req_json["operationName"] in ("searchProductV5", "SearchProductV5Query")
        assert "params" in req_json["variables"]


@pytest.mark.asyncio
async def test_parse_search_page_records_provenance_for_all_items(spider, mock_store):
    raw_items = [
        {
            "id": "101",
            "name": "ASUS Vivobook 14 Laptop",
            "url": "https://www.tokopedia.com/store/asus-vivobook-14",
            "price": {"number": 8000000},
            "category": {"breadcrumb": "komputer-laptop/laptop/consumer-laptop"},
        },
        {
            "id": "102",
            "name": "Tas Laptop Waterproof",
            "url": "https://www.tokopedia.com/store/tas-laptop",
            "price": {"number": 150000},
            "category": {"breadcrumb": "komputer-laptop/laptop/aksesoris-laptop"},
        },
        {
            "id": "103",
            "name": "Lenovo Legion Gaming Laptop",
            "url": "https://www.tokopedia.com/store/lenovo-legion",
            "price": {"number": 15000000},
            "category": {"breadcrumb": "komputer-laptop/pc-laptop-gaming/laptop-gaming"},
        },
    ]

    response = make_graphql_response(raw_items, total_data=100, page=1)
    results = [r async for r in spider.parse_search_page(response)]

    # Provenance recorded for ALL 3 items (including ineligible item 102)
    assert mock_store.record_discovery.call_count == 3

    # Product detail GET requests scheduled ONLY for eligible items (101 and 103)
    product_requests = [r for r in results if r.callback == spider.parse_product_page or r.callback == spider.parse_product]
    assert len(product_requests) == 2
    assert product_requests[0].url == "https://www.tokopedia.com/store/asus-vivobook-14"
    assert product_requests[1].url == "https://www.tokopedia.com/store/lenovo-legion"


@pytest.mark.asyncio
async def test_parse_search_page_deduplicates_products(spider):
    raw_items = [
        {
            "id": "101",
            "name": "ASUS Vivobook 14 Laptop",
            "url": "https://www.tokopedia.com/store/asus-vivobook-14",
            "price": {"number": 8000000},
            "category": {"breadcrumb": "komputer-laptop/laptop/consumer-laptop"},
        },
        {
            "id": "101",  # Duplicate item ID
            "name": "ASUS Vivobook 14 Laptop",
            "url": "https://www.tokopedia.com/store/asus-vivobook-14",
            "price": {"number": 8000000},
            "category": {"breadcrumb": "komputer-laptop/laptop/consumer-laptop"},
        },
    ]

    response = make_graphql_response(raw_items, total_data=100, page=1)
    results = [r async for r in spider.parse_search_page(response)]

    detail_requests = [r for r in results if r.url == "https://www.tokopedia.com/store/asus-vivobook-14"]
    assert len(detail_requests) == 1


@pytest.mark.asyncio
async def test_parse_search_page_stops_pagination_on_duplicate_fingerprint(spider):
    raw_items = [
        {
            "id": "101",
            "name": "ASUS Vivobook 14 Laptop",
            "url": "https://www.tokopedia.com/store/asus-vivobook-14",
            "price": {"number": 8000000},
            "category": {"breadcrumb": "komputer-laptop/laptop/consumer-laptop"},
        },
    ]

    # Page 1
    resp_1 = make_graphql_response(raw_items, total_data=100, page=1)

    with patch.object(spider, "max_pages", 5):
        # Explicitly set rows to 1 so len(products) == rows
        resp_1.meta["rows"] = 1
        results_1 = [r async for r in spider.parse_search_page(resp_1)]
        graphql_next_1 = [r for r in results_1 if (getattr(r, "method", None) or r._session_kwargs.get("method")) == "POST"]
        assert len(graphql_next_1) == 1
        assert graphql_next_1[0].meta["page"] == 2

        # Page 2 returns duplicate products -> fingerprint match
        resp_2 = make_graphql_response(raw_items, total_data=100, page=2)
        resp_2.meta["rows"] = 1
        results_2 = [r async for r in spider.parse_search_page(resp_2)]
        graphql_next_2 = [r for r in results_2 if (getattr(r, "method", None) or r._session_kwargs.get("method")) == "POST"]
        # Stopping pagination due to duplicate fingerprint
        assert len(graphql_next_2) == 0


@pytest.mark.asyncio
async def test_parse_search_page_stops_pagination_when_max_pages_reached(spider):
    raw_items = [
        {
            "id": "101",
            "name": "ASUS Vivobook 14 Laptop",
            "url": "https://www.tokopedia.com/store/asus-vivobook-14",
            "price": {"number": 8000000},
            "category": {"breadcrumb": "komputer-laptop/laptop/consumer-laptop"},
        },
    ]
    # Response for page 5 when max_pages is 5
    resp = make_graphql_response(raw_items, total_data=100, page=5)
    resp.meta["max_pages"] = 5
    resp.meta["rows"] = 1

    results = [r async for r in spider.parse_search_page(resp)]
    graphql_next = [r for r in results if (getattr(r, "method", None) or r._session_kwargs.get("method")) == "POST"]
    assert len(graphql_next) == 0
