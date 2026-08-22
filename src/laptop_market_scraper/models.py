from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SeedSource(BaseModel):
    source_type: Literal["category", "search"]
    query: str | None
    url: HttpUrl


class ListingSeed(BaseModel):
    product_url: str
    source_type: str
    source_query: str | None
    source_url: str
    source_page: int | None


class RawProduct(BaseModel):
    crawl_run_id: str
    scraped_at: datetime
    product_url: str
    source_type: str
    source_query: str | None
    source_url: str
    source_page: int | None

    product_name_raw: str | None = None
    price_raw: str | None = None
    original_price_raw: str | None = None
    discount_raw: str | None = None
    sold_count_raw: str | None = None
    view_count_raw: str | None = None
    review_count_raw: str | None = None
    rating_raw: str | None = None
    talk_count_raw: str | None = None

    product_id: str | None = None
    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    breadcrumbs: tuple[str, ...] = ()
    shop_name: str | None = None
    shop_location: str | None = None
    official_store: bool | None = None


class NormalizedProduct(BaseModel):
    crawl_run_id: str
    scraped_at: datetime
    product_name: str
    product_url: str
    canonical_url: str
    product_id: str | None = None
    listing_key: str

    price: int | None = Field(default=None, gt=0)
    original_price: int | None = Field(default=None, gt=0)
    discount_percent: float | None = Field(default=None, ge=0, le=100)

    sold_count: int | None = Field(default=None, ge=0)
    view_count: int | None = Field(default=None, ge=0)
    review_count: int | None = Field(default=None, ge=0)
    talk_count: int | None = Field(default=None, ge=0)
    transaction_success: int | None = Field(default=None, ge=0)
    transaction_reject: int | None = Field(default=None, ge=0)

    rating: float | None = Field(default=None, ge=0, le=5)
