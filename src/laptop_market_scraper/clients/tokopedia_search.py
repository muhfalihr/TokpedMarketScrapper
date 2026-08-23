"""Tokopedia searchProductV5 GraphQL request payload builder."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from laptop_market_scraper.clients.search_contract import SearchContract

GRAPHQL_URL = "https://gql.tokopedia.com/graphql/SearchProductV5Query"


def build_search_params(
    query: str,
    page: int,
    rows: int = 60,
    category_sc: str | None = "297",
    sort_code: str = "23",
) -> str:
    """Build URL-encoded query parameter string for searchProductV5 GraphQL request.

    Args:
        query: Search term string (e.g. "laptop").
        page: Page number (1-indexed).
        rows: Number of product rows per page (default 60).
        category_sc: Tokopedia category filter ID (default "297" for computers/laptops).
        sort_code: Tokopedia sort code (default "23" for relevance).

    Returns:
        URL-encoded parameter string.

    Raises:
        ValueError: If page < 1.
    """
    if page < 1:
        raise ValueError(f"page must be >= 1, got {page}")

    start = (page - 1) * rows

    params: dict[str, str] = {
        "device": "desktop",
        "navsource": "",
        "ob": str(sort_code),
        "page": str(page),
        "q": query,
        "related": "true",
        "rows": str(rows),
        "safe_search": "false",
        "scheme": "https",
        "shipping": "",
        "source": "search",
        "srp_component_id": "02.01.00.00",
        "srp_page_id": "",
        "srp_page_title": "",
        "st": "product",
        "start": str(start),
    }

    if category_sc is not None and category_sc != "":
        params["sc"] = str(category_sc)

    # Sort parameters deterministically before urlencoding
    sorted_params = dict(sorted(params.items()))
    return urlencode(sorted_params)


def build_search_payload(
    *,
    contract: SearchContract,
    query: str,
    page: int,
    rows: int = 60,
    category_sc: str | None = "297",
    sort_code: str = "23",
) -> dict[str, Any]:
    """Build Tokopedia searchProductV5 GraphQL payload dict from contract and parameters.

    Args:
        contract: Verified SearchContract domain object.
        query: Search query string (e.g. "laptop").
        page: Page number (1-indexed).
        rows: Number of product rows per page (default 60).
        category_sc: Tokopedia category filter ID (default "297").
        sort_code: Tokopedia sort code (default "23").

    Returns:
        GraphQL request dict payload with operationName, variables, and query.
    """
    params_str = build_search_params(
        query=query,
        page=page,
        rows=rows,
        category_sc=category_sc,
        sort_code=sort_code,
    )

    return {
        "operationName": contract.operation_name,
        "variables": {
            "params": params_str,
        },
        "query": contract.query,
    }
