"""Search-only catalog collection spider.

Saves products directly from the searchProductV5 GraphQL response without
visiting product detail pages — one request yields up to `rows` products.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, ClassVar

from scrapling.spiders import Request, Spider

from tokped_market_scrapper.catalog.config import load_catalog_seed_config
from tokped_market_scrapper.catalog.models import CatalogProduct
from tokped_market_scrapper.catalog.store import CatalogStore
from tokped_market_scrapper.clients.search_contract import load_search_contract
from tokped_market_scrapper.clients.tokopedia_search import GRAPHQL_URL, build_search_payload
from tokped_market_scrapper.parsers.search_api import parse_search_response
from tokped_market_scrapper.url_utils import canonicalize_product_url, search_page_fingerprint

logger = logging.getLogger(__name__)


class CatalogCollectSpider(Spider):
    """Collect multi-category catalog products from Tokopedia search."""

    name = "tokopedia_catalog_collect"

    allowed_domains: ClassVar[set[str]] = {"tokopedia.com", "gql.tokopedia.com"}

    robots_txt_obey = False

    concurrent_requests = 2
    concurrent_requests_per_domain = 1

    autothrottle_enabled = True
    autothrottle_start_delay = 2.0
    autothrottle_max_delay = 30.0

    def __init__(
        self,
        crawl_run_id: str,
        store: CatalogStore,
        seed_config: str = "config/catalog_seeds.yaml",
        contract_path: str = "config/search_product_v5_contract.json",
        max_pages: int | None = None,
        keywords_filter: tuple[str, ...] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.crawl_run_id = crawl_run_id
        self.store = store
        self.seed_config = seed_config
        self.contract_path = contract_path
        self.max_pages = max_pages
        self.keywords_filter = keywords_filter

        self.config = load_catalog_seed_config(seed_config)
        if keywords_filter:
            wanted = {k.lower() for k in keywords_filter}
            self.config = self.config.model_copy(
                update={"keywords": tuple(k for k in self.config.keywords if k.lower() in wanted)}
            )

        self.saved_unique = 0
        self.last_page_fingerprints: dict[str, str] = {}

    async def parse(self, response):
        pass

    async def start_requests(self):
        contract = load_search_contract(self.contract_path)

        # Emit only first pages; parse_search_page paginates onward per task.
        tasks = [t for t in self.config.tasks() if t.page == 1]

        logger.info(
            "Catalog collect starting: %d first-page tasks (%d keywords x %d tiers, up to page %d)",
            len(tasks),
            len(self.config.keywords),
            len(self.config.tiers),
            self.max_pages
            if self.max_pages is not None
            else self.config.max_pages_per_task,
        )

        for task in tasks:
            payload = build_search_payload(
                contract=contract,
                query=task.keyword,
                page=task.page,
                rows=task.rows,
                category_sc=self.config.category_sc,
                sort_code=self.config.sort_code,
                shop_tier=task.shop_tier,
            )

            yield Request(
                GRAPHQL_URL,
                method="POST",
                json=payload,
                callback=self.parse_search_page,
                meta={
                    "keyword": task.keyword,
                    "shop_tier": task.shop_tier,
                    "page": task.page,
                    "rows": task.rows,
                },
            )

    def _build_catalog_product(
        self,
        product: Any,
        *,
        keyword: str,
        shop_tier_filter: int | None,
        page: int,
        rank: int,
    ) -> CatalogProduct:
        canonical_url = canonicalize_product_url(product.url)
        return CatalogProduct(
            crawl_run_id=self.crawl_run_id,
            scraped_at=datetime.now(UTC),
            product_id=product.product_id,
            name=product.name,
            url=product.url,
            canonical_url=canonical_url,
            price=product.price,
            original_price_raw=product.original_price_raw,
            original_price=product.original_price,
            discount_percent=product.discount_percent,
            rating=product.rating,
            sold_label=product.sold_label,
            sold_count_floor=product.sold_count_floor,
            category_id=product.category.id if product.category.id else None,
            category_name=product.category.name,
            category_breadcrumb=product.category.breadcrumb,
            shop_id=product.shop_id,
            shop_name=product.shop_name,
            shop_city=product.shop_city,
            shop_tier=product.shop_tier,
            is_official=product.is_official,
            is_ad=product.is_ad,
            source_keyword=keyword,
            source_shop_tier_filter=shop_tier_filter,
            source_page=page,
            source_rank=rank,
            sort_code=self.config.sort_code,
        )

    async def parse_search_page(self, response):
        meta = response.meta or {}
        keyword = meta.get("keyword", "")
        shop_tier = meta.get("shop_tier")
        page = meta.get("page", 1)
        rows = meta.get("rows", 60)

        try:
            payload = response.json()
        except (ValueError, TypeError, AttributeError):
            import json

            payload = json.loads(response.text)

        search_page = parse_search_response(payload, query=keyword, page=page, rows=rows)

        for rank, product in enumerate(search_page.products, start=1):
            if not product.product_id:
                continue

            catalog_product = self._build_catalog_product(
                product,
                keyword=keyword,
                shop_tier_filter=shop_tier,
                page=page,
                rank=rank,
            )

            self.store.record_hit(
                crawl_run_id=self.crawl_run_id,
                product_id=catalog_product.product_id,
                keyword=keyword,
                page=page,
                rank_in_page=rank,
            )

            if self.store.save_product(catalog_product):
                self.saved_unique += 1

        logger.info(
            "keyword='%s' tier=%s page=%d: %d products (%d new unique, run total %d)",
            keyword,
            shop_tier,
            page,
            len(search_page.products),
            self.saved_unique,
            self.store.count_products(self.crawl_run_id),
        )

        # Duplicate-page guard: stop paginating this keyword+tier when a page repeats
        fp_key = f"{keyword}|tier={shop_tier}"
        fp = search_page_fingerprint(search_page.products)
        prev_fp = self.last_page_fingerprints.get(fp_key)
        self.last_page_fingerprints[fp_key] = fp

        if prev_fp is not None and fp == prev_fp:
            logger.warning(
                "Duplicate search page fingerprint (%s) for '%s'. Stopping this task's pagination.",
                fp[:12],
                fp_key,
            )
            return

        if len(search_page.products) != rows:
            return

        next_page = page + 1
        if next_page > self.config.max_pages_per_task:
            return
        if self.max_pages is not None and next_page > self.max_pages:
            return

        contract = load_search_contract(self.contract_path)
        next_payload = build_search_payload(
            contract=contract,
            query=keyword,
            page=next_page,
            rows=rows,
            category_sc=self.config.category_sc,
            sort_code=self.config.sort_code,
            shop_tier=shop_tier,
        )

        yield Request(
            GRAPHQL_URL,
            method="POST",
            json=next_payload,
            callback=self.parse_search_page,
            meta={
                "keyword": keyword,
                "shop_tier": shop_tier,
                "page": next_page,
                "rows": rows,
            },
        )
