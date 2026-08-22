"""Tests for the spider orchestration."""

from unittest.mock import MagicMock, patch

import pytest
from scrapling.parser import Adaptor

from laptop_market_scraper.spiders.tokopedia_laptop import TokopediaLaptopSpider


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.save.return_value = True
    return store


@pytest.fixture
def spider(mock_store):
    return TokopediaLaptopSpider(crawl_run_id="test-run", store=mock_store, max_items=2)


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
    html = '''
    <a href="https://www.tokopedia.com/shop/asus-vivobook">ASUS</a>
    <a href="https://www.tokopedia.com/shop/lenovo-loq">Lenovo</a>
    <a rel="next" href="https://www.tokopedia.com/search?page=2">Next</a>
    '''
    response = Adaptor(html, url="https://www.tokopedia.com/search?page=1")
    # Need to simulate the meta that the response brings
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
async def test_parse_product_saves_accepted_product(spider, mock_store):
    html = '''
    <h1>ASUS Vivobook Laptop 14</h1>
    <span>Rp12.000.000</span>
    '''
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
    html = '''
    <h1>Tas Laptop Anti Air</h1>
    <span>Rp150.000</span>
    '''
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
