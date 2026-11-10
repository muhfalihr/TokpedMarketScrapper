from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

from scrapling.parser import Adaptor

from tokped_market_scrapper.parsers.state import (
    TokopediaListingStateAdapter,
    _find_tokopedia_listing_container,
    _to_adaptor,
    _unwrap_payload,
    detect_flight_marker,
    extract_state_candidates,
    score_candidates,
)
from tokped_market_scrapper.url_utils import (
    build_page_url,
    is_tokopedia_product_url,
    listing_fingerprint,
)

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
    "build_page_url",
    "extract_next_page",
    "extract_product_links",
    "listing_fingerprint",
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


def _extract_page_from_url(url: str) -> int | None:
    """Extract integer page number from a URL query string if present."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        page_val = qs.get("page")
        if page_val and page_val[0]:
            val = page_val[0].strip()
            if val.isdigit():
                return int(val)
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def _resolve_pagination(
    response: object,
    current_page: int | None,
    total_pages: int | None,
    has_next_page: bool | None,
    total_products: int | None = None,
) -> tuple[int | None, int | None, bool | None]:
    """Resolve current_page, next_page, and has_next_page using the 4-priority hierarchy.

    Hierarchy:
    1. Explicit hasNextPage boolean (Priority 1)
    2. currentPage < totalPages (Priority 2)
    3. ceil(totalData / pageSize) (Priority 3, computed into total_pages upstream)
    4. DOM <a rel="next"> fallback (Priority 4)
    If no evidence: has_next_page = None, next_page = None.
    """
    base_url = str(response.url) if hasattr(response, "url") else ""
    url_page = _extract_page_from_url(base_url)
    eff_curr = current_page if current_page is not None else url_page

    # Priority 1: Explicit has_next_page
    if has_next_page is True:
        curr = eff_curr or 1
        return curr, curr + 1, True
    if has_next_page is False:
        return eff_curr, None, False

    # Priority 2 & 3: Total pages comparison
    if total_pages is not None:
        curr = eff_curr or 1
        if curr < total_pages:
            return curr, curr + 1, True
        return eff_curr, None, False

    # Priority 4: DOM rel=next fallback
    dom_next_url = _extract_dom_next_page(response)
    if dom_next_url:
        dom_next_page = _extract_page_from_url(dom_next_url)
        curr = eff_curr or 1
        next_pg = dom_next_page if dom_next_page is not None else curr + 1
        return curr, next_pg, True

    # No pagination evidence
    return eff_curr, None, None


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
                    curr, nxt, has_nxt = _resolve_pagination(
                        response,
                        res.current_page,
                        res.total_pages,
                        res.has_next_page,
                        res.total_products,
                    )

                    return ListingPageData(
                        product_urls=res.product_urls,
                        current_page=curr,
                        next_page=nxt,
                        has_next_page=has_nxt,
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

            curr, nxt, has_nxt = _resolve_pagination(
                response,
                generic_res.current_page,
                generic_res.total_pages,
                generic_res.has_next_page,
                generic_res.total_products,
            )

            return ListingPageData(
                product_urls=generic_res.product_urls,
                current_page=curr,
                next_page=nxt,
                has_next_page=has_nxt,
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

    curr, nxt, has_nxt = _resolve_pagination(response, None, None, None, None)

    return ListingPageData(
        product_urls=tuple(dom_urls),
        current_page=curr,
        next_page=nxt,
        has_next_page=has_nxt,
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

    Unified pagination discovery with state and DOM fallback.
    """
    base_url = str(response.url) if hasattr(response, "url") else ""
    page_data = parse_listing_page(response)

    if page_data.has_next_page and page_data.next_page is not None and base_url:
        return build_page_url(base_url, page_data.next_page)

    dom_next = _extract_dom_next_page(response)
    if dom_next:
        return dom_next

    return None

