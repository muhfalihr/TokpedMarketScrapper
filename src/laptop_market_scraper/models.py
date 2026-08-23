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

    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    shop_name: str | None = None
    shop_location: str | None = None
    official_store: bool | None = None

    source_type: str | None = None
    source_query: str | None = None
    source_url: str | None = None
    source_page: int | None = None


class SearchSeed(BaseModel):
    query: str
    kind: Literal["generic", "brand"]
    brand_hint: str | None = None
    max_pages: int = Field(default=20, gt=0)


class SearchCategory(BaseModel):
    id: str | None = None
    old_id: int | None = None
    name: str | None = None
    breadcrumb: str | None = None
    ga_key: str | None = None


class SearchProduct(BaseModel):
    product_id: str
    name: str
    url: str
    price: int | None = None
    original_price_raw: str | None = None
    discount_percent: float | None = None
    shop_id: str | None = None
    shop_name: str | None = None
    shop_city: str | None = None
    rating: float | None = None
    stock: int | None = None
    category: SearchCategory = Field(default_factory=SearchCategory)
    raw: dict = Field(default_factory=dict)


class SearchPage(BaseModel):
    query: str
    page: int
    rows: int
    products: tuple[SearchProduct, ...] = ()
    total_data: int | None = None


class FeatureProvenance(BaseModel):
    crawl_run_id: str
    listing_key: str
    feature_name: str
    source_layer: Literal["graphql_search", "product_detail_html", "derived", "unknown"]
    source_field: str
    value_kind: str = "numeric"
    raw_value_json: str | None = None
    observed_at: str


