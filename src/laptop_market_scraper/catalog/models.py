"""Domain models for the multi-category catalog pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

CRAWLER_VERSION = "v2.1.0-catalog"

SORT_LABELS: dict[str, str] = {
    "23": "relevance",
    "9": "latest",
    "12": "cheap",
    "14": "expensive",
    "36": "top_seller",
    "5": "rating",
}


class CatalogTask(BaseModel):
    """A single collect unit: one keyword under one shop_tier filter, one page."""

    keyword: str
    shop_tier: int | None = None
    page: int = Field(default=1, ge=1)
    rows: int = Field(default=60, ge=1)


class CatalogSeedConfig(BaseModel):
    """Parsed catalog seed configuration."""

    rows: int = Field(default=60, ge=1)
    category_sc: str | None = None
    sort_code: str = "23"
    max_pages_per_task: int = Field(default=2, ge=1)
    tiers: tuple[int, ...] = (2, 1)
    keywords: tuple[str, ...] = ()
    seed_url: HttpUrl | None = None

    def tasks(self) -> list[CatalogTask]:
        """Expand keywords × tiers × pages into collect tasks."""
        expanded: list[CatalogTask] = []
        for keyword in self.keywords:
            for tier in self.tiers:
                for page in range(1, self.max_pages_per_task + 1):
                    expanded.append(
                        CatalogTask(keyword=keyword, shop_tier=tier, page=page, rows=self.rows)
                    )
        return expanded


class CatalogProduct(BaseModel):
    """A product observed from the search layer, stored directly without PDP visits."""

    crawl_run_id: str
    scraped_at: datetime
    product_id: str
    name: str
    url: str
    canonical_url: str

    price: int | None = Field(default=None, gt=0)
    original_price_raw: str | None = None
    original_price: int | None = Field(default=None, gt=0)
    discount_percent: float | None = Field(default=None, ge=0, le=100)

    rating: float | None = Field(default=None, ge=0, le=5)
    sold_label: str | None = None
    sold_count_floor: int | None = Field(default=None, ge=0)

    category_id: str | None = None
    category_name: str | None = None
    category_breadcrumb: str | None = None

    shop_id: str | None = None
    shop_name: str | None = None
    shop_city: str | None = None
    shop_tier: int | None = None
    is_official: bool | None = None
    is_ad: bool | None = None

    source_keyword: str
    source_shop_tier_filter: int | None = None
    source_page: int = Field(ge=1)
    source_rank: int = Field(ge=1)
    sort_code: str = "23"


class EnrichmentResult(BaseModel):
    """Outcome of one product-detail-page enrichment attempt."""

    crawl_run_id: str
    product_id: str
    status: Literal["ok", "partial", "fail"]
    review_count: int | None = Field(default=None, ge=0)
    sold: int | None = Field(default=None, ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    category_id: str | None = None
    error: str | None = None
    enriched_at: datetime
