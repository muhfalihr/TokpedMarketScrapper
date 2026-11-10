"""Product-detail field extraction.

Extraction hierarchy: JSON-LD → embedded structured JSON → semantic DOM text.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from scrapling.parser import Adaptor

from laptop_market_scraper.models import ListingSeed, RawProduct


def extract_jsonld_product(response: Adaptor) -> dict[str, Any] | None:
    """Extract Product-typed JSON-LD from the page, if present."""
    for script in response.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text)
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(data, dict) and data.get("@type") == "Product":
            return data

        # Handle @graph wrapping
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item

    return None


def extract_embedded_json_values(response: Adaptor) -> dict[str, Any]:
    """Search for embedded JSON objects containing product data.

    Scans all script tags for JSON with product-related keys.
    """
    result: dict[str, Any] = {}

    for script in response.css("script"):
        text = script.text or ""
        # Look for JSON object literals in script content
        for match in re.finditer(r"\{[^{}]{20,}\}", text):
            try:
                obj = json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                continue

            if "name" in obj and "price" in obj:
                result.update(obj)
                break

    return result


def extract_dom_fallback(response: Adaptor) -> dict[str, str | None]:
    """Extract product fields from DOM text as a last resort."""
    result: dict[str, str | None] = {}

    # Product name from h1
    h1 = response.css("h1")
    result["product_name_raw"] = h1[0].text.strip() if h1 else None

    # Collect all text from spans and other elements
    all_text = response.get_all_text() if hasattr(response, "get_all_text") else ""

    # Also collect individual span texts for more targeted extraction
    span_texts = [s.text.strip() for s in response.css("span") if s.text]

    # Price - look for Rp patterns
    for text in span_texts:
        if re.match(r"Rp[\d.]+", text):
            result["price_raw"] = text
            break
    else:
        price_match = re.search(r"Rp[\d.]+", all_text)
        result["price_raw"] = price_match.group() if price_match else None

    # Sold count
    for text in span_texts:
        if re.search(r"terjual", text, re.IGNORECASE):
            result["sold_count_raw"] = text
            break
    else:
        sold_match = re.search(
            r"[\d.,]+(?:rb|jt|k)?\+?\s*terjual", all_text, re.IGNORECASE
        )
        result["sold_count_raw"] = sold_match.group().strip() if sold_match else None

    # Rating
    for text in span_texts:
        if re.match(r"^\d[.,]\d$", text.strip()):
            result["rating_raw"] = text.strip()
            break
    else:
        rating_match = re.search(r"\b(\d[.,]\d)\b", all_text)
        result["rating_raw"] = rating_match.group(1) if rating_match else None

    # Review count
    for text in span_texts:
        if re.search(r"ulasan|review", text, re.IGNORECASE):
            result["review_count_raw"] = text
            break
    else:
        review_match = re.search(r"(\d+)\s*(?:ulasan|review)", all_text, re.IGNORECASE)
        result["review_count_raw"] = review_match.group().strip() if review_match else None

    return result



def parse_product(
    response: Adaptor,
    seed: ListingSeed,
    crawl_run_id: str,
) -> RawProduct:
    """Parse a product detail page into a RawProduct.

    Uses a three-tier extraction hierarchy:
    1. JSON-LD structured data
    2. Embedded JSON in scripts
    3. DOM text fallback

    Never fails the whole crawl because one optional metric is absent.
    product_name_raw and URL are the only mandatory identity fields.
    """
    url = str(response.url) if hasattr(response, "url") else seed.product_url

    # Tier 1: JSON-LD
    jsonld = extract_jsonld_product(response)
    # Tier 2: Embedded JSON
    embedded = extract_embedded_json_values(response)
    # Tier 3: DOM fallback
    dom = extract_dom_fallback(response)

    # Merge data with priority: JSON-LD > embedded > DOM
    product_name_raw = None
    price_raw = None
    rating_raw = None
    review_count_raw = None
    sold_count_raw = None
    brand = None

    if jsonld:
        product_name_raw = jsonld.get("name")
        offers = jsonld.get("offers", {})
        if isinstance(offers, dict):
            price_raw = offers.get("price")
        aggregate_rating = jsonld.get("aggregateRating", {})
        if isinstance(aggregate_rating, dict):
            rating_raw = aggregate_rating.get("ratingValue")
            review_count_raw = aggregate_rating.get("reviewCount")
        brand_data = jsonld.get("brand", {})
        if isinstance(brand_data, dict):
            brand = brand_data.get("name")
        elif isinstance(brand_data, str):
            brand = brand_data

    if embedded:
        product_name_raw = product_name_raw or embedded.get("name")
        price_raw = price_raw or str(embedded.get("price", "")) or None
        rating_raw = rating_raw or str(embedded.get("ratingValue", "")) or None

    # DOM fallback fills remaining gaps
    product_name_raw = product_name_raw or dom.get("product_name_raw")
    price_raw = price_raw or dom.get("price_raw")
    sold_count_raw = sold_count_raw or dom.get("sold_count_raw")
    rating_raw = rating_raw or dom.get("rating_raw")
    review_count_raw = review_count_raw or dom.get("review_count_raw")

    # Convert to string if not already
    price_raw = str(price_raw) if price_raw is not None else None
    rating_raw = str(rating_raw) if rating_raw is not None else None
    review_count_raw = str(review_count_raw) if review_count_raw is not None else None

    return RawProduct(
        crawl_run_id=crawl_run_id,
        scraped_at=datetime.now(UTC),
        product_url=url,
        source_type=seed.source_type,
        source_query=seed.source_query,
        source_url=seed.source_url,
        source_page=seed.source_page,
        product_name_raw=product_name_raw,
        price_raw=price_raw,
        sold_count_raw=sold_count_raw,
        rating_raw=rating_raw,
        review_count_raw=review_count_raw,
        brand=brand,
    )
