"""Scrapling crawl orchestration."""

from __future__ import annotations

import logging
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from scrapling.spiders import Request, Spider

from laptop_market_scraper.config import load_seeds
from laptop_market_scraper.eligibility import is_laptop_candidate
from laptop_market_scraper.models import ListingSeed
from laptop_market_scraper.parsers.listing import parse_listing_page
from laptop_market_scraper.parsers.product import parse_product
from laptop_market_scraper.storage import SQLiteStore, normalize_product

logger = logging.getLogger(__name__)


class TokopediaLaptopSpider(Spider):
    name = "tokopedia_laptops"

    allowed_domains: ClassVar[set[str]] = {"tokopedia.com"}

    robots_txt_obey = False

    concurrent_requests = 4
    concurrent_requests_per_domain = 1

    autothrottle_enabled = True
    autothrottle_start_delay = 2.0
    autothrottle_max_delay = 60.0

    def __init__(
        self,
        crawl_run_id: str,
        store: SQLiteStore | None = None,
        seed_config: str = "config/seeds.yaml",
        max_items: int | None = None,
        browser_fallback: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.crawl_run_id = crawl_run_id
        self.store = store
        self.seed_config = seed_config
        self.max_items = max_items
        self.browser_fallback = browser_fallback
        self.items_scraped = 0

    async def parse(self, response):
        pass

    async def start_requests(self):
        seeds = load_seeds(self.seed_config)
        for seed in seeds:
            yield Request(
                url=str(seed.url),
                callback=self.parse_listing,
                meta={
                    "source_type": seed.source_type,
                    "source_query": seed.query,
                    "source_url": str(seed.url),
                    "source_page": 1,
                },
            )

    async def parse_listing(self, response):
        meta = response.meta or {}
        listing_data = parse_listing_page(response)

        logger.info(
            "Parsed listing page %s: %d product URLs discovered (dom_fallback=%s, source=%s, next_page=%s)",
            getattr(response, "url", "unknown"),
            len(listing_data.product_urls),
            listing_data.dom_fallback_used,
            listing_data.state_source,
            listing_data.next_page,
        )

        for link in listing_data.product_urls:
            if self.max_items and self.items_scraped >= self.max_items:
                break

            yield Request(
                url=link,
                callback=self.parse_product_page,
                meta={
                    "source_type": meta.get("source_type"),
                    "source_query": meta.get("source_query"),
                    "source_url": meta.get("source_url"),
                    "source_page": meta.get("source_page", 1),
                },
            )

        if (
            (not self.max_items or self.items_scraped < self.max_items)
            and listing_data.has_next_page
            and listing_data.next_page
        ):
            current_url = str(getattr(response, "url", "") or meta.get("source_url", ""))
            if current_url:
                parsed = urlparse(current_url)
                qs = parse_qs(parsed.query, keep_blank_values=True)
                qs["page"] = [str(listing_data.next_page)]
                next_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

                new_meta = meta.copy()
                new_meta["source_page"] = listing_data.next_page
                yield Request(
                    url=next_url,
                    callback=self.parse_listing,
                    meta=new_meta,
                )

    async def parse_product_page(self, response):
        meta = response.meta or {}
        seed = ListingSeed(
            product_url=response.url,
            source_type=meta.get("source_type", "unknown"),
            source_query=meta.get("source_query"),
            source_url=meta.get("source_url", ""),
            source_page=meta.get("source_page"),
        )
        raw_product = parse_product(response, seed, self.crawl_run_id)

        if not is_laptop_candidate(raw_product.product_name_raw or "", raw_product.breadcrumbs):
            if self.store:
                self.store.save_rejected(raw_product, "Failed laptop eligibility checks")
            return

        normalized = normalize_product(raw_product)
        if self.store:
            saved = self.store.save(normalized)
            if saved:
                self.items_scraped += 1
        else:
            self.items_scraped += 1

        yield normalized
