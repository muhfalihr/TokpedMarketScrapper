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


def test_start_requests_yields_from_seeds(spider):
    with patch("laptop_market_scraper.spiders.tokopedia_laptop.load_seeds") as mock_load:
        mock_seed = MagicMock()
        mock_seed.url = "https://example.com"
        mock_seed.source_type = "search"
        mock_seed.query = "laptop"
        mock_load.return_value = [mock_seed]

        requests = list(spider.start_requests())

        assert len(requests) == 1
        req = requests[0]
        assert req.url == "https://example.com"
        # We need to access meta dictionary
        assert hasattr(req, "meta") or isinstance(req.meta, dict)


def test_parse_listing_yields_product_requests_and_next_page(spider):
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

    results = list(spider.parse_listing(response))

    # We expect 2 product requests and 1 next page request
    assert len(results) == 3
    assert results[0].url == "https://www.tokopedia.com/shop/asus-vivobook"
    assert results[1].url == "https://www.tokopedia.com/shop/lenovo-loq"
    assert results[2].url == "https://www.tokopedia.com/search?page=2"
    assert results[2].meta["source_page"] == 2


def test_parse_product_saves_accepted_product(spider, mock_store):
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

    results = list(spider.parse_product_page(response))

    assert len(results) == 1
    assert mock_store.save.called
    assert not mock_store.save_rejected.called


def test_parse_product_rejects_accessory(spider, mock_store):
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

    results = list(spider.parse_product_page(response))

    assert len(results) == 0
    assert not mock_store.save.called
    assert mock_store.save_rejected.called
