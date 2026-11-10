"""PDP enrichment: fetch product detail pages for review_count and exact sold.

Extraction hierarchy per product page:
1. ``window.__cache`` (Apollo normalized cache) -> ``pdpBasicInfo<id>`` entity,
   resolving ``stats`` (``countReview``, ``rating``) and ``txStats``
   (``countSold``) references; legacy ``__APOLLO_STATE__`` inline variant kept.
2. JSON-LD Product block (``aggregateRating.reviewCount`` / ``ratingValue``)
3. DOM regex fallback for the sold label ("... terjual")
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, ClassVar

from scrapling.spiders import Request, Spider

from laptop_market_scraper.catalog.models import EnrichmentResult
from laptop_market_scraper.catalog.store import CatalogStore
from laptop_market_scraper.parsers.search_api import parse_sold_label

logger = logging.getLogger(__name__)

_APOLLO_RE = re.compile(
    r"__APOLLO_STATE__\s*=\s*(\{.*?\})\s*;?\s*(?:</script>|$)",
    re.DOTALL,
)
_CACHE_ASSIGN_RE = re.compile(r"window\.__cache\s*=\s*")
_SOLD_DOM_RE = re.compile(r"([\d.,]+(?:rb|jt|k)?\+?)\s*terjual", re.IGNORECASE)


class PdpMetrics:
    """Best-effort metrics extracted from one product detail page."""

    __slots__ = ("category_id", "rating", "review_count", "sold", "sources")

    def __init__(self) -> None:
        self.review_count: int | None = None
        self.sold: int | None = None
        self.rating: float | None = None
        self.category_id: str | None = None
        self.sources: set[str] = set()

    @property
    def any_found(self) -> bool:
        return any(
            (
                self.review_count is not None,
                self.sold is not None,
                self.rating is not None,
                self.category_id is not None,
            )
        )


def _find_basic_info(node: Any, depth: int = 0) -> Mapping[str, Any] | None:
    """Recursively locate the first dict containing a 'basicInfo' key."""
    if depth > 12:
        return None
    if isinstance(node, Mapping):
        candidate = node.get("basicInfo")
        if isinstance(candidate, Mapping):
            return candidate
        for value in node.values():
            found = _find_basic_info(value, depth + 1)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_basic_info(item, depth + 1)
            if found is not None:
                return found
    return None


def _extract_balanced_json(html: str, start: int) -> Any | None:
    """Extract a balanced JSON object starting at ``start`` (must point at '{')."""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, min(start + 5_000_000, len(html))):
        char = html[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _extract_window_cache(html: str) -> Mapping[str, Any] | None:
    """Extract the ``window.__cache`` Apollo normalized cache, when present."""
    match = _CACHE_ASSIGN_RE.search(html)
    if match is None:
        return None
    brace_at = html.find("{", match.end())
    if brace_at == -1:
        return None
    cache = _extract_balanced_json(html, brace_at)
    return cache if isinstance(cache, Mapping) else None


def _resolve_ref(cache: Mapping[str, Any], value: Any) -> Any:
    """Resolve an Apollo reference ``{"type": "id", "id": ...}`` against the cache."""
    if isinstance(value, Mapping) and value.get("type") == "id":
        target_id = value.get("id")
        if isinstance(target_id, str):
            return cache.get(target_id)
    return value


def _find_pdp_basic_info(cache: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Locate the ``pdpBasicInfo<id>`` entity inside a normalized Apollo cache."""
    for key, value in cache.items():
        if isinstance(key, str) and key.startswith("pdpBasicInfo") and isinstance(value, Mapping):
            return value
    return None


def _to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _apply_basic_info(
    metrics: PdpMetrics,
    basic_info: Mapping[str, Any],
    cache: Mapping[str, Any] | None = None,
) -> None:
    """Fill metrics from a basicInfo entity, resolving Apollo refs via cache."""
    stats = basic_info.get("stats")
    if cache is not None:
        stats = _resolve_ref(cache, stats)
    if isinstance(stats, Mapping):
        review = _to_int(stats.get("countReview"))
        rating = _to_float(stats.get("rating"))
        if review is not None:
            metrics.review_count = review
            metrics.sources.add("apollo")
        if rating is not None:
            metrics.rating = rating
            metrics.sources.add("apollo")

    tx_stats = basic_info.get("txStats")
    if cache is not None:
        tx_stats = _resolve_ref(cache, tx_stats)
    if isinstance(tx_stats, Mapping):
        sold = _to_int(tx_stats.get("countSold"))
        if sold is not None:
            metrics.sold = sold
            metrics.sources.add("apollo")

    category = basic_info.get("category")
    if cache is not None:
        category = _resolve_ref(cache, category)
    if isinstance(category, Mapping) and category.get("id") is not None:
        metrics.category_id = str(category["id"])
        metrics.sources.add("apollo")


def extract_pdp_metrics_from_html(html: str) -> PdpMetrics:
    """Extract enrichment metrics from a product detail page HTML string.

    Args:
        html: Full HTML source of the product page.

    Returns:
        PdpMetrics with whatever tiers succeeded (possibly none).
    """
    metrics = PdpMetrics()

    # Tier 1a: window.__cache — Apollo normalized cache (current Tokopedia PDP)
    cache = _extract_window_cache(html)
    if cache is not None:
        basic_info = _find_pdp_basic_info(cache)
        if basic_info is not None:
            _apply_basic_info(metrics, basic_info, cache=cache)

    # Tier 1b: legacy __APOLLO_STATE__ with inline basicInfo
    if not metrics.sources:
        apollo_match = _APOLLO_RE.search(html)
        if apollo_match is not None:
            try:
                apollo = json.loads(apollo_match.group(1))
                basic_info = _find_basic_info(apollo)
                if isinstance(basic_info, Mapping):
                    _apply_basic_info(metrics, basic_info)
            except json.JSONDecodeError:
                logger.debug("Apollo state JSON failed to parse; falling back", exc_info=True)

    # Tier 2: JSON-LD Product
    if metrics.review_count is None or metrics.rating is None:
        for match in re.finditer(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        ):
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for candidate in candidates:
                if not isinstance(candidate, Mapping) or candidate.get("@type") != "Product":
                    continue
                agg = candidate.get("aggregateRating")
                if isinstance(agg, Mapping):
                    if metrics.review_count is None:
                        metrics.review_count = _to_int(agg.get("reviewCount"))
                    if metrics.rating is None:
                        metrics.rating = _to_float(agg.get("ratingValue"))
                    metrics.sources.add("jsonld")
                break

    # Tier 3: DOM sold label fallback
    if metrics.sold is None:
        dom_match = _SOLD_DOM_RE.search(html)
        if dom_match is not None:
            metrics.sold = parse_sold_label(dom_match.group(0))
            if metrics.sold is not None:
                metrics.sources.add("dom")

    return metrics


def extract_pdp_metrics(response: Any) -> PdpMetrics:
    """Extract enrichment metrics from a scrapling response/Adaptor."""
    html = getattr(response, "html_content", None) or getattr(response, "body", b"")
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    return extract_pdp_metrics_from_html(str(html))


class CatalogEnrichSpider(Spider):
    """Enrich catalog products by fetching their product detail pages."""

    name = "tokopedia_catalog_enrich"

    allowed_domains: ClassVar[set[str]] = {"tokopedia.com", "gql.tokopedia.com"}

    robots_txt_obey = False

    concurrent_requests = 4
    concurrent_requests_per_domain = 2

    autothrottle_enabled = True
    autothrottle_start_delay = 1.0
    autothrottle_max_delay = 30.0

    def __init__(
        self,
        crawl_run_id: str,
        store: CatalogStore,
        limit: int | None = None,
        retry_failed: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.crawl_run_id = crawl_run_id
        self.store = store
        self.limit = limit
        self.retry_failed = retry_failed

        self.ok_count = 0
        self.fail_count = 0

    async def parse(self, response):
        pass

    async def start_requests(self):
        pending = self.store.pending_enrichment(
            self.crawl_run_id,
            limit=self.limit,
            retry_failed=self.retry_failed,
        )
        logger.info(
            "Enrichment run '%s': %d pending products (limit=%s, retry_failed=%s)",
            self.crawl_run_id,
            len(pending),
            self.limit,
            self.retry_failed,
        )

        for product_id, url in pending:
            yield Request(
                url,
                callback=self.parse_pdp,
                meta={"product_id": product_id},
            )

    async def parse_pdp(self, response):
        meta = response.meta or {}
        product_id = str(meta.get("product_id", ""))

        try:
            metrics = extract_pdp_metrics(response)
        except Exception:  # noqa: BLE001 — enrichment tidak boleh menggagalkan spider
            metrics = PdpMetrics()

        if metrics.any_found:
            status = "ok" if metrics.review_count is not None else "partial"
            self.ok_count += 1
        else:
            status = "fail"
            self.fail_count += 1

        self.store.save_enrichment(
            EnrichmentResult(
                crawl_run_id=self.crawl_run_id,
                product_id=product_id,
                status=status,
                review_count=metrics.review_count,
                sold=metrics.sold,
                rating=metrics.rating,
                category_id=metrics.category_id,
                error=None if metrics.any_found else "no metrics extracted",
                enriched_at=datetime.now(UTC),
            )
        )

        yield {
            "product_id": product_id,
            "status": status,
            "review_count": metrics.review_count,
            "sold": metrics.sold,
        }
