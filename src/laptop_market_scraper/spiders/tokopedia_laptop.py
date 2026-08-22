"""Scrapling crawl orchestration."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from scrapling.spiders import Request, Spider

from laptop_market_scraper.config import load_seeds
from laptop_market_scraper.eligibility import is_laptop_candidate
from laptop_market_scraper.models import ListingSeed
from laptop_market_scraper.parsers.listing import parse_listing_page
from laptop_market_scraper.parsers.product import parse_product
from laptop_market_scraper.storage import SQLiteStore, normalize_product
from laptop_market_scraper.url_utils import build_page_url, listing_fingerprint

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
        max_pages: int | None = None,
        browser_fallback: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.crawl_run_id = crawl_run_id
        self.store = store
        self.seed_config = seed_config
        self.max_items = max_items
        self.max_pages = max_pages
        self.browser_fallback = browser_fallback
        self.items_scraped = 0
        self.seen_listing_fingerprints: set[str] = set()

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
        current_url = str(getattr(response, "url", "") or meta.get("source_url", ""))
        source_page = meta.get("source_page", listing_data.current_page or 1)

        # 1. Page Fingerprinting & Repeated Product Set Detection
        fp = listing_fingerprint(listing_data.product_urls)
        is_duplicate = False
        if listing_data.product_urls:
            if fp in self.seen_listing_fingerprints:
                logger.warning(
                    "Duplicate listing fingerprint detected (%s) for URL %s (page %s). Stopping pagination.",
                    fp[:12],
                    current_url,
                    source_page,
                )
                is_duplicate = True
            else:
                self.seen_listing_fingerprints.add(fp)

        logger.info(
            "Parsed listing page %s: %d product URLs discovered (dom_fallback=%s, source=%s, next_page=%s, fp=%s)",
            current_url,
            len(listing_data.product_urls),
            listing_data.dom_fallback_used,
            listing_data.state_source,
            listing_data.next_page,
            fp[:8] if fp else "empty",
        )

        # 2. Yield product requests if max_items not yet reached
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
                    "source_page": source_page,
                },
            )

        # 3. Pagination Safety Checks
        # Stop on duplicate listing content
        if is_duplicate:
            return

        # Stop if max_items reached
        if self.max_items and self.items_scraped >= self.max_items:
            return

        # Stop if max_pages limit reached on current page
        if self.max_pages is not None and source_page >= self.max_pages:
            logger.info(
                "Reached max_pages limit (%d >= %d) for %s. Stopping pagination.",
                source_page,
                self.max_pages,
                current_url,
            )
            return

        # Stop if no next page evidence
        if not (listing_data.has_next_page and listing_data.next_page):
            return

        # Stop if next_page exceeds max_pages
        if self.max_pages is not None and listing_data.next_page > self.max_pages:
            logger.info(
                "Next page %d exceeds max_pages limit (%d). Stopping pagination.",
                listing_data.next_page,
                self.max_pages,
            )
            return

        if not current_url:
            return

        # Construct next URL safely preserving query parameters
        next_url = build_page_url(current_url, listing_data.next_page)

        # Stop on self-referential URL loop
        if not next_url or next_url == current_url:
            logger.warning(
                "Self-referential next page URL detected (%s == %s). Stopping pagination.",
                next_url,
                current_url,
            )
            return

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
