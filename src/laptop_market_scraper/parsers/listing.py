"""Unified listing parser for Tokopedia search and category pages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from scrapling.parser import Adaptor

from laptop_market_scraper.parsers.state import (
    TokopediaListingStateAdapter,
    _find_tokopedia_listing_container,
    _to_adaptor,
    _unwrap_payload,
    detect_flight_marker,
    extract_state_candidates,
    score_candidates,
)
from laptop_market_scraper.url_utils import is_tokopedia_product_url

logger = logging.getLogger(__name__)

_TOKOPEDIA_DOMAIN = "tokopedia.com"

_NON_PRODUCT_PATH_PREFIXES = (
    "/search",
    "/p/",
    "/hot/",
    "/discovery/",
    "/find/",
)

__all__ = (
    "ListingDiagnostics",
    "ListingPageData",
    "extract_next_page",
    "extract_product_links",
    "parse_listing_page",
)


@dataclass
class ListingDiagnostics:
    """Diagnostic telemetry gathered during listing page parsing."""

    scripts_scanned: int = 0
    state_candidates_found: int = 0
    json_decode_errors: int = 0
    next_f_detected: bool = False
    product_records_seen: int = 0
    product_urls_accepted: int = 0
    product_urls_rejected: int = 0
    dom_fallback_used: bool = False


@dataclass(frozen=True)
class ListingPageData:
    """Structured extraction result from a listing or search page."""

    product_urls: tuple[str, ...]
    current_page: int | None
    next_page: int | None
    has_next_page: bool | None
    total_products: int | None
    state_source: str | None
    dom_fallback_used: bool
    diagnostics: ListingDiagnostics


def _is_product_link(url: str, base_domain: str = _TOKOPEDIA_DOMAIN) -> bool:
    """Return True if *url* looks like a product detail page on the target domain."""
    if not is_tokopedia_product_url(url):
        return False
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return base_domain in host


def _extract_dom_product_links(response: object) -> list[str]:
    """Extract product links using DOM-only selectors without state parsing."""
    seen: set[str] = set()
    result: list[str] = []
    base_url = str(response.url) if hasattr(response, "url") else ""
    page = _to_adaptor(response) if not isinstance(response, Adaptor) else response

    for anchor in (page.css("a[href]") if hasattr(page, "css") else []):
        href = anchor.attrib.get("href", "")
        if not href:
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        if not _is_product_link(absolute, _TOKOPEDIA_DOMAIN):
            continue
        if absolute not in seen:
            seen.add(absolute)
            result.append(absolute)

    return result


def _extract_dom_next_page(response: object) -> str | None:
    """Find the next-page link using DOM-only selectors."""
    base_url = str(response.url) if hasattr(response, "url") else ""
    page = _to_adaptor(response) if not isinstance(response, Adaptor) else response

    if hasattr(page, "css"):
        for anchor in page.css('a[rel="next"]'):
            href = anchor.attrib.get("href", "")
            if href:
                return urljoin(base_url, href)

    return None


def _compute_next_page(
    current_page: int | None,
    total_pages: int | None,
    has_next_page: bool | None,
) -> int | None:
    """Determine the next page number from pagination indicators."""
    if current_page is None:
        return None
    if has_next_page is True:
        return current_page + 1
    if has_next_page is None and total_pages is not None and current_page < total_pages:
        return current_page + 1
    return None


def parse_listing_page(response: object) -> ListingPageData:
    """Unified entry point to parse a Tokopedia listing/search page.

    Execution flow:
    1. Scan scripts and extract embedded state candidates.
    2. Try TokopediaListingStateAdapter on candidates.
       If adapter yields products, returns ListingPageData(dom_fallback_used=False).
    3. If adapter yields no products, try generic recovery and candidate scoring.
    4. If state yields 0 products or is missing, fall back to DOM parsing
       (dom_fallback_used=True).

    Returns frozen ListingPageData containing deduplicated product URLs,
    pagination metadata, state source, and diagnostic telemetry.
    """
    diagnostics = ListingDiagnostics()

    page = _to_adaptor(response) if not isinstance(response, Adaptor) else response
    scripts = page.css("script") if hasattr(page, "css") else []
    diagnostics.scripts_scanned = len(scripts)
    diagnostics.next_f_detected = detect_flight_marker(response)

    def _record_decode_error(exc: Exception, marker: str, idx: int) -> None:
        diagnostics.json_decode_errors += 1

    candidates = extract_state_candidates(response, on_decode_error=_record_decode_error)
    diagnostics.state_candidates_found = len(candidates)

    adapter = TokopediaListingStateAdapter()

    # 1. Try dedicated Tokopedia state adapter
    for cand in candidates:
        if adapter.supports(cand.payload):
            try:
                res = adapter.extract(cand)
                unwrapped = _unwrap_payload(cand.payload)
                container = _find_tokopedia_listing_container(unwrapped)
                if container and isinstance(container.get("products"), (list, tuple)):
                    raw_prods = container["products"]
                    diagnostics.product_records_seen = len(raw_prods)
                    diagnostics.product_urls_accepted = len(res.product_urls)
                    diagnostics.product_urls_rejected = max(
                        0, len(raw_prods) - len(res.product_urls)
                    )
                else:
                    diagnostics.product_records_seen = len(res.product_urls)
                    diagnostics.product_urls_accepted = len(res.product_urls)
                    diagnostics.product_urls_rejected = 0

                if res.product_urls:
                    diagnostics.dom_fallback_used = False
                    next_page = _compute_next_page(
                        res.current_page, res.total_pages, res.has_next_page
                    )

                    return ListingPageData(
                        product_urls=res.product_urls,
                        current_page=res.current_page,
                        next_page=next_page,
                        has_next_page=res.has_next_page,
                        total_products=res.total_products,
                        state_source=cand.source or "tokopedia_adapter",
                        dom_fallback_used=False,
                        diagnostics=diagnostics,
                    )
            except (KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
                logger.debug("Failed adapter extraction on candidate %s: %s", cand.source, exc)

    # 2. Try generic recovery if candidates exist but adapter yielded no products
    if candidates:
        scored = score_candidates(candidates)
        if scored and scored[0].product_count > 0:
            best = scored[0]
            generic_res = best.to_listing_result(source="generic_recovery")
            diagnostics.product_records_seen = best.product_count
            diagnostics.product_urls_accepted = best.product_count
            diagnostics.product_urls_rejected = 0
            diagnostics.dom_fallback_used = False

            next_page = _compute_next_page(
                generic_res.current_page, generic_res.total_pages, generic_res.has_next_page
            )

            return ListingPageData(
                product_urls=generic_res.product_urls,
                current_page=generic_res.current_page,
                next_page=next_page,
                has_next_page=generic_res.has_next_page,
                total_products=generic_res.total_products,
                state_source=best.candidate.source or "generic_recovery",
                dom_fallback_used=False,
                diagnostics=diagnostics,
            )

    # 3. Fall back to DOM parsing
    diagnostics.dom_fallback_used = True
    base_url = str(response.url) if hasattr(response, "url") else ""
    dom_urls: list[str] = []
    seen_urls: set[str] = set()

    anchors = page.css("a[href]") if hasattr(page, "css") else []
    diagnostics.product_records_seen = len(anchors)

    for anchor in anchors:
        href = anchor.attrib.get("href", "")
        if not href:
            diagnostics.product_urls_rejected += 1
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        if _is_product_link(absolute, _TOKOPEDIA_DOMAIN):
            if absolute not in seen_urls:
                seen_urls.add(absolute)
                dom_urls.append(absolute)
                diagnostics.product_urls_accepted += 1
            else:
                diagnostics.product_urls_rejected += 1
        else:
            diagnostics.product_urls_rejected += 1

    # DOM Pagination
    next_url_dom: str | None = None
    for anchor in (page.css('a[rel="next"]') if hasattr(page, "css") else []):
        href = anchor.attrib.get("href", "")
        if href:
            next_url_dom = urljoin(base_url, href)
            break

    current_page = None
    next_page = None
    has_next_page = None

    if base_url:
        parsed_base = urlparse(base_url)
        qs_base = parse_qs(parsed_base.query)
        if "page" in qs_base and qs_base["page"] and qs_base["page"][0].isdigit():
            current_page = int(qs_base["page"][0])

    if next_url_dom:
        has_next_page = True
        parsed_next = urlparse(next_url_dom)
        qs_next = parse_qs(parsed_next.query)
        if "page" in qs_next and qs_next["page"] and qs_next["page"][0].isdigit():
            next_page = int(qs_next["page"][0])
        elif current_page is not None:
            next_page = current_page + 1
        else:
            next_page = 2
            if current_page is None:
                current_page = 1
    else:
        if dom_urls:
            has_next_page = False

    return ListingPageData(
        product_urls=tuple(dom_urls),
        current_page=current_page,
        next_page=next_page,
        has_next_page=has_next_page,
        total_products=None,
        state_source=None,
        dom_fallback_used=True,
        diagnostics=diagnostics,
    )


def extract_product_links(response: object) -> list[str]:
    """Extract unique, same-domain product URLs from a listing page response.

    Unified discovery delegating to parse_listing_page.
    """
    page_data = parse_listing_page(response)
    return list(page_data.product_urls)


def extract_next_page(response: object) -> str | None:
    """Find the next-page link from a listing page response.

    Unified pagination discovery with DOM fallback.
    """
    base_url = str(response.url) if hasattr(response, "url") else ""
    page = _to_adaptor(response) if not isinstance(response, Adaptor) else response

    # Check DOM first for explicit <a rel="next">
    if hasattr(page, "css"):
        for anchor in page.css('a[rel="next"]'):
            href = anchor.attrib.get("href", "")
            if href:
                return urljoin(base_url, href)

    # Check structured listing page data
    page_data = parse_listing_page(response)
    if page_data.has_next_page and page_data.next_page is not None and base_url:
        parsed = urlparse(base_url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs["page"] = [str(page_data.next_page)]
        return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    return None
