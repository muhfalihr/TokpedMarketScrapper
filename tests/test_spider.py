"""Tests for the spider orchestration and unified listing parser integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scrapling.parser import Adaptor

from laptop_market_scraper.parsers.listing import ListingDiagnostics, ListingPageData
from laptop_market_scraper.spiders.tokopedia_laptop import TokopediaLaptopSpider

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.save.return_value = True
    return store


@pytest.fixture
def spider(mock_store):
    return TokopediaLaptopSpider(crawl_run_id="test-run", store=mock_store, max_items=10)


@pytest.mark.asyncio
async def test_start_requests_yields_from_seeds(spider):
    with patch("laptop_market_scraper.spiders.tokopedia_laptop.load_seeds") as mock_load:
        mock_seed = MagicMock()
        mock_seed.url = "https://example.com"
        mock_seed.source_type = "search"
        mock_seed.query = "laptop"
        mock_load.return_value = [mock_seed]

        requests = [r async for r in spider.start_requests()]
        assert len(requests) == 1
        req = requests[0]
        assert req.url == "https://example.com"
        assert req.callback == spider.parse_listing


@pytest.mark.asyncio
async def test_parse_listing_yields_product_requests_and_next_page(spider):
    html = """
    <a href="https://www.tokopedia.com/shop/asus-vivobook">ASUS</a>
    <a href="https://www.tokopedia.com/shop/lenovo-loq">Lenovo</a>
    <a rel="next" href="https://www.tokopedia.com/search?page=2">Next</a>
    """
    response = Adaptor(html, url="https://www.tokopedia.com/search?page=1")
    response.meta = {
        "source_type": "search",
        "source_query": "laptop",
        "source_url": "https://www.tokopedia.com/search?page=1",
        "source_page": 1,
    }

    results = [r async for r in spider.parse_listing(response)]

    assert len(results) == 3
    assert results[0].url == "https://www.tokopedia.com/shop/asus-vivobook"
    assert results[1].url == "https://www.tokopedia.com/shop/lenovo-loq"
    assert "page=2" in results[2].url


@pytest.mark.asyncio
async def test_parse_listing_calls_parse_listing_page_once(spider):
    """Verify parse_listing invokes parse_listing_page exactly once per listing response."""
    html = "<html><body></body></html>"
    response = Adaptor(html, url="https://www.tokopedia.com/search?q=laptop")
    response.meta = {
        "source_type": "search",
        "source_query": "laptop",
        "source_url": "https://www.tokopedia.com/search?q=laptop",
        "source_page": 1,
    }

    mock_page_data = ListingPageData(
        product_urls=(
            "https://www.tokopedia.com/shop/product-1",
            "https://www.tokopedia.com/shop/product-2",
        ),
        current_page=1,
        next_page=2,
        has_next_page=True,
        total_products=50,
        state_source="__NEXT_DATA__",
        dom_fallback_used=False,
        diagnostics=ListingDiagnostics(),
    )

    with patch(
        "laptop_market_scraper.spiders.tokopedia_laptop.parse_listing_page",
        return_value=mock_page_data,
    ) as mock_parser:
        results = [r async for r in spider.parse_listing(response)]

        mock_parser.assert_called_once_with(response)
        assert len(results) == 3
        assert results[0].url == "https://www.tokopedia.com/shop/product-1"
        assert results[1].url == "https://www.tokopedia.com/shop/product-2"
        assert "page=2" in results[2].url
        assert results[2].meta["source_page"] == 2


@pytest.mark.asyncio
async def test_parse_listing_with_embedded_state_fixture(spider):
    """Verify parse_listing parses Next.js embedded state fixture and yields product & next requests."""
    html = (FIXTURE_DIR / "tokopedia_search_state.html").read_text(encoding="utf-8")
    response = Adaptor(html, url="https://www.tokopedia.com/search?st=product&q=laptop")
    response.meta = {
        "source_type": "search",
        "source_query": "laptop",
        "source_url": "https://www.tokopedia.com/search?st=product&q=laptop",
        "source_page": 1,
    }

    results = [r async for r in spider.parse_listing(response)]

    # 3 product URLs + 1 next page request
    assert len(results) == 4
    assert results[0].url.startswith("https://www.tokopedia.com/asus-official/")
    assert results[1].url.startswith("https://www.tokopedia.com/lenovo-gaming/")
    assert results[2].url.startswith("https://www.tokopedia.com/acer-store/")
    # Next page request has page=2 and callback parse_listing
    assert "page=2" in results[3].url
    assert results[3].callback == spider.parse_listing
    assert results[3].meta["source_page"] == 2


@pytest.mark.asyncio
async def test_parse_listing_respects_max_items(mock_store):
    """Verify parse_listing stops yielding requests when max_items has been reached."""
    spider = TokopediaLaptopSpider(crawl_run_id="test-run", store=mock_store, max_items=2)
    spider.items_scraped = 2

    html = """
    <a href="https://www.tokopedia.com/shop/asus-1">ASUS 1</a>
    <a href="https://www.tokopedia.com/shop/asus-2">ASUS 2</a>
    <a href="https://www.tokopedia.com/shop/asus-3">ASUS 3</a>
    <a rel="next" href="https://www.tokopedia.com/search?page=2">Next</a>
    """
    response = Adaptor(html, url="https://www.tokopedia.com/search?page=1")
    response.meta = {
        "source_type": "search",
        "source_query": "laptop",
        "source_url": "https://www.tokopedia.com/search?page=1",
        "source_page": 1,
    }

    results = [r async for r in spider.parse_listing(response)]

    # 0 requests should be yielded because max_items is already reached
    assert len(results) == 0


@pytest.mark.asyncio
async def test_parse_product_saves_accepted_product(spider, mock_store):
    html = """
    <h1>ASUS Vivobook Laptop 14</h1>
    <span>Rp12.000.000</span>
    """
    response = Adaptor(html, url="https://www.tokopedia.com/shop/asus-vivobook")
    response.meta = {
        "source_type": "search",
        "source_query": "laptop",
        "source_url": "https://www.tokopedia.com/search?page=1",
        "source_page": 1,
    }

    results = [r async for r in spider.parse_product_page(response)]

    assert len(results) == 1
    normalized = results[0]
    assert normalized.product_name == "ASUS Vivobook Laptop 14"
    mock_store.save.assert_called_once()
    assert spider.items_scraped == 1


@pytest.mark.asyncio
async def test_parse_product_rejects_accessory(spider, mock_store):
    html = """
    <h1>Tas Laptop Anti Air</h1>
    <span>Rp150.000</span>
    """
    response = Adaptor(html, url="https://www.tokopedia.com/shop/tas-laptop")
    response.meta = {
        "source_type": "search",
        "source_query": "laptop",
        "source_url": "https://www.tokopedia.com/search?page=1",
        "source_page": 1,
    }

    results = [r async for r in spider.parse_product_page(response)]

    assert len(results) == 0
    mock_store.save_rejected.assert_called_once()
