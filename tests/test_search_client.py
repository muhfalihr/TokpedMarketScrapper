"""Unit tests for Tokopedia searchProductV5 GraphQL request builder."""

from pathlib import Path
from urllib.parse import parse_qsl

import pytest

from laptop_market_scraper.clients.search_contract import load_search_contract
from laptop_market_scraper.clients.tokopedia_search import (
    GRAPHQL_URL,
    build_search_params,
    build_search_payload,
)

CONTRACT_PATH = Path("config/search_product_v5_contract.json")


@pytest.fixture
def sample_contract():
    return load_search_contract(CONTRACT_PATH)


def test_graphql_url_constant():
    """Verify GRAPHQL_URL constant points to correct Tokopedia GraphQL search endpoint."""
    assert GRAPHQL_URL == "https://gql.tokopedia.com/graphql/SearchProductV5Query"


def test_build_search_params_page_one():
    """Verify page 1 yields start=0 with default search parameters."""
    params_str = build_search_params(query="laptop", page=1)
    params = dict(parse_qsl(params_str))

    assert params["q"] == "laptop"
    assert params["page"] == "1"
    assert params["start"] == "0"
    assert params["rows"] == "60"
    assert params["sc"] == "297"
    assert params["ob"] == "23"
    assert params["device"] == "desktop"
    assert params["source"] == "search"
    assert params["st"] == "product"
    assert params["scheme"] == "https"
    assert params["related"] == "true"
    assert params["safe_search"] == "false"


def test_build_search_params_page_two():
    """Verify page 2 yields start=60 for rows=60."""
    params_str = build_search_params(query="laptop", page=2, rows=60)
    params = dict(parse_qsl(params_str))

    assert params["q"] == "laptop"
    assert params["page"] == "2"
    assert params["start"] == "60"
    assert params["rows"] == "60"
    assert params["sc"] == "297"
    assert params["ob"] == "23"


def test_build_search_params_page_three():
    """Verify page 3 yields start=120 for rows=60."""
    params_str = build_search_params(query="laptop", page=3, rows=60)
    params = dict(parse_qsl(params_str))

    assert params["q"] == "laptop"
    assert params["page"] == "3"
    assert params["start"] == "120"
    assert params["rows"] == "60"


def test_build_search_params_custom_arguments():
    """Verify custom rows, category_sc, and sort_code parameters."""
    params_str = build_search_params(
        query="macbook",
        page=2,
        rows=30,
        category_sc="298",
        sort_code="2",
    )
    params = dict(parse_qsl(params_str))

    assert params["q"] == "macbook"
    assert params["page"] == "2"
    assert params["start"] == "30"
    assert params["rows"] == "30"
    assert params["sc"] == "298"
    assert params["ob"] == "2"


def test_build_search_params_invalid_page():
    """Verify ValueError is raised when page < 1."""
    with pytest.raises(ValueError, match="page must be >= 1"):
        build_search_params(query="laptop", page=0)


def test_build_search_params_no_category():
    """Verify sc is omitted when category_sc is None or empty."""
    params_str = build_search_params(query="laptop", page=1, category_sc=None)
    params = dict(parse_qsl(params_str))
    assert "sc" not in params


def test_build_search_payload_structure(sample_contract):
    """Verify build_search_payload returns dictionary matching contract specs."""
    payload = build_search_payload(
        contract=sample_contract,
        query="laptop gaming",
        page=1,
    )

    assert isinstance(payload, dict)
    assert payload["operationName"] == sample_contract.operation_name
    assert payload["query"] == sample_contract.query
    assert "variables" in payload
    assert "params" in payload["variables"]

    params = dict(parse_qsl(payload["variables"]["params"]))
    assert params["q"] == "laptop gaming"
    assert params["page"] == "1"
    assert params["start"] == "0"
