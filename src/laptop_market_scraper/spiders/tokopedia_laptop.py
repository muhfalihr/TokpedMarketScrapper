"""Scrapling crawl orchestration with searchProductV5 GraphQL search & safe pagination."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from scrapling.spiders import Request, Spider

from laptop_market_scraper.clients.search_contract import load_search_contract
from laptop_market_scraper.clients.tokopedia_search import GRAPHQL_URL, build_search_payload
from laptop_market_scraper.config import load_search_config, load_seeds
from laptop_market_scraper.eligibility import evaluate_laptop_eligibility, is_laptop_candidate
from laptop_market_scraper.models import ListingSeed
from laptop_market_scraper.parsers.listing import parse_listing_page
from laptop_market_scraper.parsers.product import parse_product
from laptop_market_scraper.parsers.search_api import parse_search_response
from laptop_market_scraper.storage import SQLiteStore, normalize_product
from laptop_market_scraper.url_utils import (
    build_page_url,
    canonicalize_product_url,
    listing_fingerprint,
    make_listing_key,
    search_page_fingerprint,
)

logger = logging.getLogger(__name__)


class TokopediaLaptopSpider(Spider):
    name = "tokopedia_laptops"

    allowed_domains: ClassVar[set[str]] = {"tokopedia.com", "gql.tokopedia.com"}

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
        contract_path: str = "config/search_product_v5_contract.json",
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
        self.contract_path = contract_path
        self.max_items = max_items
        self.max_pages = max_pages
        self.browser_fallback = browser_fallback

        self.items_scraped = 0
        self.accepted_unique_count = 0
        self.seen_listing_fingerprints: set[str] = set()
        self.seen_listing_keys: set[str] = set()
        self.last_page_fingerprints: dict[str, str] = {}

    async def parse(self, response):
        pass

    async def start_requests(self):
        contract = load_search_contract(self.contract_path)
        search_cfg = load_search_config(self.seed_config)
        seeds = load_seeds(self.seed_config)

        rows = search_cfg.get("rows", 60)
        category_sc = search_cfg.get("category_sc", "297")
        sort_code = search_cfg.get("sort_code", "23")

        for seed in seeds:
            query = getattr(seed, "query", "")
            kind = getattr(seed, "kind", "generic")
            if not isinstance(kind, str):
                kind = "generic"
            brand_hint = getattr(seed, "brand_hint", None)
            if not isinstance(brand_hint, str):
                brand_hint = None

            seed_max_pages = getattr(seed, "max_pages", 20)
            if not isinstance(seed_max_pages, int):
                seed_max_pages = 20

            max_p = self.max_pages if self.max_pages is not None else seed_max_pages

            payload = build_search_payload(
                contract=contract,
                query=query,
                page=1,
                rows=rows,
                category_sc=category_sc,
                sort_code=sort_code,
            )

            yield Request(
                GRAPHQL_URL,
                method="POST",
                json=payload,
                callback=self.parse_search_page,
                meta={
                    "source_type": "search",
                    "source_query": query,
                    "seed_kind": kind,
                    "brand_hint": brand_hint,
                    "page": 1,
                    "rows": rows,
                    "category_sc": category_sc,
                    "sort_code": sort_code,
                    "max_pages": max_p,
                },
            )

    async def parse_search_page(self, response):
        meta = response.meta or {}
        query = meta.get("source_query", "")
        page = meta.get("page", 1)
        rows = meta.get("rows", 60)
        category_sc = meta.get("category_sc", "297")
        sort_code = meta.get("sort_code", "23")
        max_p = meta.get("max_pages", 20)
        if self.max_pages is not None:
            max_p = self.max_pages

        try:
            payload = response.json()
        except Exception:
            import json
            payload = json.loads(response.text)

        search_page = parse_search_response(
            payload,
            query=query,
            page=page,
            rows=rows,
        )

        for rank, product in enumerate(search_page.products, start=1):
            canonical_url = canonicalize_product_url(product.url)
            listing_key = make_listing_key(product.product_id, canonical_url)

            # 1. Record discovery provenance in SQLite for ALL products before eligibility filtering
            if self.store:
                self.store.record_discovery(
                    crawl_run_id=self.crawl_run_id,
                    listing_key=listing_key,
                    source_query=query,
                    seed_kind=meta.get("seed_kind", "generic"),
                    search_page=page,
                    search_start=(page - 1) * rows,
                    search_rows=rows,
                    search_rank=rank,
                    category_sc=category_sc,
                    sort_code=sort_code,
                    observed_total_data=search_page.total_data,
                    product_name=getattr(product, "name", None),
                    category_breadcrumb=getattr(product.category, "breadcrumb", None) if getattr(product, "category", None) else None,
                )

            # 2. Evaluate laptop eligibility
            eligibility = evaluate_laptop_eligibility(product)

            # 3. Schedule product detail GET request if accepted and unique
            if eligibility.accepted:
                if listing_key not in self.seen_listing_keys:
                    self.seen_listing_keys.add(listing_key)
                    self.accepted_unique_count += 1

                    if self.max_items is None or self.accepted_unique_count <= self.max_items:
                        yield Request(
                            url=product.url,
                            callback=self.parse_product_page,
                            meta={
                                "source_type": "search",
                                "source_query": query,
                                "source_url": product.url,
                                "source_page": page,
                                "seed_kind": meta.get("seed_kind"),
                            },
                        )

        # Safe Pagination
        fp = search_page_fingerprint(search_page.products)
        prev_fp = self.last_page_fingerprints.get(query)
        self.last_page_fingerprints[query] = fp

        if prev_fp is not None and fp == prev_fp:
            logger.warning(
                "Duplicate search page fingerprint (%s) detected for query '%s' page %d. Stopping pagination.",
                fp[:12],
                query,
                page,
            )
            return

        if len(search_page.products) != rows:
            return

        if page >= max_p:
            logger.info(
                "Reached max_pages limit (%d >= %d) for query '%s'. Stopping pagination.",
                page,
                max_p,
                query,
            )
            return

        if self.max_items is not None and self.accepted_unique_count >= self.max_items:
            logger.info(
                "Reached max_items limit (%d >= %d). Stopping pagination.",
                self.accepted_unique_count,
                self.max_items,
            )
            return

        next_page = page + 1
        contract = load_search_contract(self.contract_path)
        next_payload = build_search_payload(
            contract=contract,
            query=query,
            page=next_page,
            rows=rows,
            category_sc=category_sc,
            sort_code=sort_code,
        )
        next_meta = meta.copy()
        next_meta["page"] = next_page
        yield Request(
            GRAPHQL_URL,
            method="POST",
            json=next_payload,
            callback=self.parse_search_page,
            meta=next_meta,
        )

    async def parse_listing(self, response):
        """Legacy HTML listing parser preserved for backwards compatibility."""
        meta = response.meta or {}
        listing_data = parse_listing_page(response)
        current_url = str(getattr(response, "url", "") or meta.get("source_url", ""))
        source_page = meta.get("source_page", listing_data.current_page or 1)

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

        if is_duplicate:
            return

        if self.max_items and self.items_scraped >= self.max_items:
            return

        if self.max_pages is not None and source_page >= self.max_pages:
            logger.info(
                "Reached max_pages limit (%d >= %d) for %s. Stopping pagination.",
                source_page,
                self.max_pages,
                current_url,
            )
            return

        if not (listing_data.has_next_page and listing_data.next_page):
            return

        if self.max_pages is not None and listing_data.next_page > self.max_pages:
            logger.info(
                "Next page %d exceeds max_pages limit (%d). Stopping pagination.",
                listing_data.next_page,
                self.max_pages,
            )
            return

        if not current_url:
            return

        next_url = build_page_url(current_url, listing_data.next_page)

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

        yield normalized.model_dump()

    parse_product = parse_product_page
