from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from laptop_market_scraper.models import SearchCategory, SearchPage, SearchProduct

logger = logging.getLogger(__name__)

__all__ = (
    "SearchGraphQLError",
    "SearchSchemaError",
    "parse_idr_price",
    "parse_search_response",
    "parse_sold_label",
)

_SOLD_LABEL_RE = re.compile(r"^\s*([\d.,]+)\s*(rb|jt)?\s*\+?\s*terjual", re.IGNORECASE)
_IDR_PRICE_RE = re.compile(r"rp\s*([\d.,]+)", re.IGNORECASE)


def parse_sold_label(label: str | None) -> int | None:
    """Parse a Tokopedia sold label into its numeric floor value.

    Examples:
        "19 terjual" -> 19
        "100+ terjual" -> 100
        "1,2jt terjual" -> 1200000 (jt = juta/million)
        "2rb terjual" -> 2000 (rb = ribu/thousand)

    Args:
        label: Raw sold label text (e.g. from labelGroups ri_product_credibility).

    Returns:
        Integer floor value of the sold count, or None when unparsable.
    """
    if not label or not isinstance(label, str):
        return None

    match = _SOLD_LABEL_RE.match(label)
    if match is None:
        return None

    number_text = match.group(1).replace(",", ".")
    try:
        value = float(number_text)
    except ValueError:
        return None

    lowered = label.lower()
    if "jt" in lowered:
        value *= 1_000_000
    elif "rb" in lowered:
        value *= 1_000

    return int(value)


def parse_idr_price(text: str | None) -> int | None:
    """Parse a formatted IDR price string (e.g. "Rp120.000") into an integer.

    Args:
        text: Formatted price string.

    Returns:
        Integer rupiah value, or None when unparsable.
    """
    if not text or not isinstance(text, str):
        return None

    match = _IDR_PRICE_RE.search(text)
    if match is None:
        return None

    digits = match.group(1).replace(".", "").replace(",", "")
    try:
        return int(digits)
    except ValueError:
        return None


def _extract_sold_label(item: Mapping[str, Any]) -> str | None:
    """Extract sold label from labelGroups position 'ri_product_credibility'."""
    for group in item.get("labelGroups") or []:
        if not isinstance(group, Mapping):
            continue
        if group.get("position") == "ri_product_credibility":
            title = group.get("title")
            return str(title) if title else None
    return None


def _extract_is_official(item: Mapping[str, Any], shop_tier: int | None) -> bool | None:
    """Detect official-store status from badge URL or shop tier."""
    badge = item.get("badge")
    if isinstance(badge, Mapping):
        badge_url = str(badge.get("url") or "")
        if "official_store" in badge_url:
            return True
    if shop_tier is not None:
        return shop_tier == 2
    return None


def _extract_is_ad(item: Mapping[str, Any]) -> bool | None:
    """Detect advertisement placement from the ads object."""
    ads = item.get("ads")
    if not isinstance(ads, Mapping):
        return None
    ads_id = str(ads.get("id") or "")
    tag = ads.get("tag")
    return bool(ads_id) or (isinstance(tag, int) and tag != 0)


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
            original_price = parse_idr_price(original_price_raw)
            disc = price_dict.get("discountPercentage")
            try:
                discount_percent = float(disc) if disc is not None else None
            except (ValueError, TypeError):
                discount_percent = None
        else:
            price = None
            original_price_raw = None
            original_price = None
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
            s_tier = shop_dict.get("tier")
            try:
                shop_tier = int(s_tier) if s_tier is not None else None
            except (ValueError, TypeError):
                shop_tier = None
        else:
            shop_id = None
            shop_name = None
            shop_city = None
            shop_tier = None

        # Sold label (bucketed, e.g. "100+ terjual") and numeric floor
        sold_label = _extract_sold_label(item)
        sold_count_floor = parse_sold_label(sold_label)

        # Official-store and advertisement flags
        is_official = _extract_is_official(item, shop_tier)
        is_ad = _extract_is_ad(item)

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
                original_price=original_price,
                discount_percent=discount_percent,
                shop_id=shop_id,
                shop_name=shop_name,
                shop_city=shop_city,
                shop_tier=shop_tier,
                rating=rating,
                stock=stock,
                sold_label=sold_label,
                sold_count_floor=sold_count_floor,
                is_official=is_official,
                is_ad=is_ad,
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
