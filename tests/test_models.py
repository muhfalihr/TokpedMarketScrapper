from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from laptop_market_scraper.models import NormalizedProduct


def test_normalized_product_rejects_invalid_rating():
    with pytest.raises(ValidationError):
        NormalizedProduct(
            crawl_run_id="run-1",
            scraped_at=datetime.now(UTC),
            product_name="ASUS Vivobook",
            product_url="https://www.tokopedia.com/shop/product",
            canonical_url="https://www.tokopedia.com/shop/product",
            listing_key="abc",
            price=10_000_000,
            rating=6.0,
        )


def test_normalized_product_accepts_missing_engagement():
    item = NormalizedProduct(
        crawl_run_id="run-1",
        scraped_at=datetime.now(UTC),
        product_name="ASUS Vivobook",
        product_url="https://www.tokopedia.com/shop/product",
        canonical_url="https://www.tokopedia.com/shop/product",
        listing_key="abc",
        price=10_000_000,
        rating=None,
        sold_count=None,
        review_count=None,
    )

    assert item.sold_count is None
