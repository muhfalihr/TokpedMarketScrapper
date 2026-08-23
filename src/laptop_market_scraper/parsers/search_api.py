from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from laptop_market_scraper.models import SearchCategory, SearchPage, SearchProduct

logger = logging.getLogger(__name__)

__all__ = (
    "SearchGraphQLError",
    "SearchSchemaError",
    "parse_search_response",
)


class SearchGraphQLError(Exception):
    """Raised when the GraphQL response contains top-level errors."""



class SearchSchemaError(Exception):
    """Raised when the response payload does not conform to expected searchProductV5 schema."""



def parse_search_response(
    payload: Mapping[str, Any] | list,
    *,
    query: str,
    page: int,
    rows: int = 60,
) -> SearchPage:
    """Parse Tokopedia searchProductV5 GraphQL response into a typed SearchPage domain model.

    Args:
        payload: Top-level dict or list response payload from GraphQL endpoint.
        query: Search query string.
        page: Page number.
        rows: Rows per page (default 60).

    Returns:
        SearchPage containing parsed SearchProduct items and total_data count.

    Raises:
        SearchGraphQLError: If top-level 'errors' key is present in response.
        SearchSchemaError: If expected schema path is missing or invalid.
    """
    if isinstance(payload, list):
        if not payload:
            raise SearchSchemaError("Response payload is an empty list")
        root = payload[0]
    elif isinstance(payload, Mapping):
        root = payload
    else:
        raise SearchSchemaError(f"Invalid payload type: {type(payload)}")

    if not isinstance(root, Mapping):
        raise SearchSchemaError(f"Root payload element is not a dict: {type(root)}")

    if root.get("errors"):
        raise SearchGraphQLError(f"GraphQL error response: {root['errors']}")

    data = root.get("data")
    if not isinstance(data, Mapping):
        raise SearchSchemaError("Missing or invalid 'data' object in response payload")

    search_data = None
    if "searchProductV5" in data and isinstance(data["searchProductV5"], Mapping):
        search_data = data["searchProductV5"]
    elif "SearchProductV5Query" in data and isinstance(data["SearchProductV5Query"], Mapping):
        search_data = data["SearchProductV5Query"]

    if search_data is None:
        raise SearchSchemaError(
            "Missing 'searchProductV5' or 'SearchProductV5Query' in response data"
        )

    # Extract total_data from header
    header = search_data.get("header")
    total_data = None
    if isinstance(header, Mapping):
        tot_raw = header.get("totalData")
        if tot_raw is not None:
            try:
                total_data = int(tot_raw)
            except (ValueError, TypeError):
                total_data = None

    # Extract products list from inner data
    inner_data = search_data.get("data")
    if not isinstance(inner_data, Mapping) or "products" not in inner_data:
        raise SearchSchemaError("Missing 'data.products' in searchProductV5 response")

    raw_products = inner_data.get("products")
    if not isinstance(raw_products, list):
        raise SearchSchemaError("'products' field is not a list")

    parsed_products: list[SearchProduct] = []

    for item in raw_products:
        if not isinstance(item, Mapping):
            continue

        item_id = item.get("id")
        if item_id is None:
            continue

        product_id = str(item_id)
        name = str(item.get("name", ""))
        url = str(item.get("url", ""))

        # Price parsing
        price_dict = item.get("price")
        if isinstance(price_dict, Mapping):
            p_num = price_dict.get("number")
            price = int(p_num) if p_num is not None else None
            orig = price_dict.get("original")
            original_price_raw = str(orig) if orig is not None else None
            disc = price_dict.get("discountPercentage")
            try:
                discount_percent = float(disc) if disc is not None else None
            except (ValueError, TypeError):
                discount_percent = None
        else:
            price = None
            original_price_raw = None
            discount_percent = None

        # Shop parsing
        shop_dict = item.get("shop")
        if isinstance(shop_dict, Mapping):
            s_id = shop_dict.get("id")
            shop_id = str(s_id) if s_id is not None else None
            s_name = shop_dict.get("name")
            shop_name = str(s_name) if s_name is not None else None
            s_city = shop_dict.get("city")
            shop_city = str(s_city) if s_city is not None else None
        else:
            shop_id = None
            shop_name = None
            shop_city = None

        # Rating parsing
        r_val = item.get("rating")
        if r_val is not None and r_val != "":
            try:
                rating = float(r_val)
            except (ValueError, TypeError):
                rating = None
        else:
            rating = None

        # Stock parsing
        st_val = item.get("stock")
        if st_val is not None and not isinstance(st_val, (dict, list, tuple)):
            try:
                stock = int(st_val)
            except (ValueError, TypeError):
                stock = None
        else:
            stock = None

        # Category parsing
        cat_dict = item.get("category")
        if isinstance(cat_dict, Mapping):
            c_id = cat_dict.get("id")
            cat_id = str(c_id) if c_id is not None else None

            c_old_id = (
                cat_dict.get("oldID")
                if "oldID" in cat_dict
                else cat_dict.get("old_id")
            )
            if c_old_id is not None:
                try:
                    old_id = int(c_old_id)
                except (ValueError, TypeError):
                    old_id = None
            else:
                old_id = None

            cat_name = cat_dict.get("name")
            breadcrumb = cat_dict.get("breadcrumb")
            ga_key = (
                cat_dict.get("gaKey")
                if "gaKey" in cat_dict
                else cat_dict.get("ga_key")
            )

            category = SearchCategory(
                id=cat_id,
                old_id=old_id,
                name=cat_name,
                breadcrumb=breadcrumb,
                ga_key=ga_key,
            )
        else:
            category = SearchCategory()

        # Retain raw item
        raw_item = dict(item)

        parsed_products.append(
            SearchProduct(
                product_id=product_id,
                name=name,
                url=url,
                price=price,
                original_price_raw=original_price_raw,
                discount_percent=discount_percent,
                shop_id=shop_id,
                shop_name=shop_name,
                shop_city=shop_city,
                rating=rating,
                stock=stock,
                category=category,
                raw=raw_item,
            )
        )

    return SearchPage(
        query=query,
        page=page,
        rows=rows,
        products=parsed_products,
        total_data=total_data,
    )
