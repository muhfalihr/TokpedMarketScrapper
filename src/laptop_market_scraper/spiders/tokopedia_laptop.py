"""Scrapling crawl orchestration."""

from typing import Any

from scrapling.spiders import Request, Spider

from laptop_market_scraper.config import load_seeds
from laptop_market_scraper.eligibility import is_laptop_candidate
from laptop_market_scraper.models import ListingSeed
from laptop_market_scraper.parsers.listing import extract_next_page, extract_product_links
from laptop_market_scraper.parsers.product import parse_product
from laptop_market_scraper.storage import SQLiteStore, normalize_product
from laptop_market_scraper.url_utils import canonicalize_product_url


class TokopediaLaptopSpider(Spider):
    name = "tokopedia_laptops"

    allowed_domains = {"tokopedia.com"}

    robots_txt_obey = True

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

    def parse(self, response):
        pass

    def start_requests(self):
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
                }
            )

    def parse_listing(self, response):
        meta = response.meta
        product_links = extract_product_links(response)

        for link in product_links:
            if self.max_items and self.items_scraped >= self.max_items:
                break

            yield Request(
                url=link,
                callback=self.parse_product_page,
                meta={
                    "source_type": meta.get("source_type"),
                    "source_query": meta.get("source_query"),
                    "source_url": meta.get("source_url"),
                    "source_page": meta.get("source_page"),
                }
            )

        if not self.max_items or self.items_scraped < self.max_items:
            next_url = extract_next_page(response)
            if next_url:
                new_meta = meta.copy()
                new_meta["source_page"] += 1
                yield Request(
                    url=next_url,
                    callback=self.parse_listing,
                    meta=new_meta
                )

    def parse_product_page(self, response):
        meta = response.meta
        seed = ListingSeed(
            product_url=str(response.url) if hasattr(response, "url") else meta.get("source_url"),
            source_type=meta.get("source_type", "unknown"),
            source_query=meta.get("source_query"),
            source_url=meta.get("source_url", ""),
            source_page=meta.get("source_page"),
        )

        raw_product = parse_product(response, seed, self.crawl_run_id)

        title = raw_product.product_name_raw or ""
        breadcrumbs = raw_product.breadcrumbs or ()

        if not is_laptop_candidate(title, breadcrumbs):
            if self.store:
                self.store.save_rejected(raw_product, "Not a laptop candidate")
            return

        normalized = normalize_product(raw_product)
        if self.store:
            saved = self.store.save(normalized)
            if saved:
                self.items_scraped += 1
        else:
            self.items_scraped += 1

        yield normalized
