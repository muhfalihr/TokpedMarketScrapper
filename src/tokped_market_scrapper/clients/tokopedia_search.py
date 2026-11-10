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
    shop_tier: int | None = None,
    pmin: int | None = None,
    pmax: int | None = None,
) -> str:
    """Build URL-encoded query parameter string for searchProductV5 GraphQL request.

    Args:
        query: Search term string (e.g. "laptop").
        page: Page number (1-indexed).
        rows: Number of product rows per page (default 60).
        category_sc: Tokopedia category filter ID (default "297" for computers/laptops).
            Pass None or "" to search across all categories (multi-category mode).
        sort_code: Tokopedia sort code (default "23" for relevance).
        shop_tier: Optional shop tier filter (2 = Official Store, 1 = Gold Merchant).
        pmin: Optional minimum price filter (rupiah).
        pmax: Optional maximum price filter (rupiah).

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

    if shop_tier is not None:
        params["shop_tier"] = str(shop_tier)

    if pmin is not None:
        params["pmin"] = str(pmin)

    if pmax is not None:
        params["pmax"] = str(pmax)

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
    shop_tier: int | None = None,
    pmin: int | None = None,
    pmax: int | None = None,
) -> dict[str, Any]:
    """Build Tokopedia searchProductV5 GraphQL payload dict from contract and parameters.

    Args:
        contract: Verified SearchContract domain object.
        query: Search query string (e.g. "laptop").
        page: Page number (1-indexed).
        rows: Number of product rows per page (default 60).
        category_sc: Tokopedia category filter ID (default "297").
            Pass None or "" to search across all categories (multi-category mode).
        sort_code: Tokopedia sort code (default "23" for relevance).
        shop_tier: Optional shop tier filter (2 = Official Store, 1 = Gold Merchant).
        pmin: Optional minimum price filter (rupiah).
        pmax: Optional maximum price filter (rupiah).

    Returns:
        GraphQL request dict payload with operationName, variables, and query.
    """
    params_str = build_search_params(
        query=query,
        page=page,
        rows=rows,
        category_sc=category_sc,
        sort_code=sort_code,
        shop_tier=shop_tier,
        pmin=pmin,
        pmax=pmax,
    )

    return {
        "operationName": contract.operation_name,
        "variables": {
            "params": params_str,
        },
        "query": contract.query,
    }
