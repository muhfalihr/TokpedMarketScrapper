"""Embedded state candidate discovery and extraction for listing pages."""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from scrapling.parser import Adaptor

from tokped_market_scrapper.url_utils import is_tokopedia_product_url

logger = logging.getLogger(__name__)

KNOWN_STATE_MARKERS: tuple[str, ...] = (
    "window.__INITIAL_STATE__",
    "window.__PRELOADED_STATE__",
    "window.__APOLLO_STATE__",
    "window.__NEXT_DATA__",
    "window.__STATE__",
    "__INITIAL_STATE__",
    "__PRELOADED_STATE__",
    "__APOLLO_STATE__",
)

FLIGHT_MARKER: str = "self.__next_f"

__all__ = (
    "FLIGHT_MARKER",
    "KNOWN_STATE_MARKERS",
    "CandidateScore",
    "StateCandidate",
    "StateListingResult",
    "TokopediaListingStateAdapter",
    "decode_json_assignment",
    "detect_flight_marker",
    "extract_generic_state",
    "extract_state_candidates",
    "looks_like_product_record",
    "score_candidate",
    "score_candidates",
    "walk_json",
)


@dataclass(frozen=True)
class StateCandidate:
    """Represents a discovered candidate embedded application state."""

    source: str
    payload: object
    script_index: int


def decode_json_assignment(
    script_text: str,
    marker: str,
) -> object | None:
    """Extract and decode a JSON object/array assigned to a JS marker using raw_decode.

    Searches for marker, locates the assignment operator '=', skips whitespace,
    finds the opening brace '{' or bracket '[', and parses the exact JSON payload via
    json.JSONDecoder().raw_decode().

    Returns the parsed object/array, or None if marker/assignment is absent or malformed.
    """
    if not script_text or marker not in script_text:
        return None

    marker_pos = script_text.find(marker)
    decoder = json.JSONDecoder()

    while marker_pos != -1:
        # Search for '=' after marker
        eq_pos = script_text.find("=", marker_pos + len(marker))
        if eq_pos == -1:
            break

        # Check characters between marker and '=': should only be whitespace
        between_marker_eq = script_text[marker_pos + len(marker) : eq_pos].strip()
        if between_marker_eq != "":
            marker_pos = script_text.find(marker, marker_pos + 1)
            continue

        # Look for opening '{' or '[' after '='
        brace_pos = script_text.find("{", eq_pos + 1)
        bracket_pos = script_text.find("[", eq_pos + 1)

        candidates = [p for p in (brace_pos, bracket_pos) if p != -1]
        if not candidates:
            marker_pos = script_text.find(marker, eq_pos + 1)
            continue

        start_pos = min(candidates)
        # Check text between '=' and start_pos (should only be whitespace)
        between_eq_start = script_text[eq_pos + 1 : start_pos].strip()
        if between_eq_start != "":
            marker_pos = script_text.find(marker, eq_pos + 1)
            continue

        try:
            payload, _ = decoder.raw_decode(script_text, start_pos)
            return payload
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
            logger.debug("Failed to decode JSON assignment for marker %s: %s", marker, exc)
            marker_pos = script_text.find(marker, eq_pos + 1)

    return None


def detect_flight_marker(response_or_text: object) -> bool:
    """Check if the response or text contains Next.js Flight/RSC stream markers."""
    if isinstance(response_or_text, str):
        return FLIGHT_MARKER in response_or_text

    if hasattr(response_or_text, "css"):
        for s in response_or_text.css("script"):
            if s.text and FLIGHT_MARKER in s.text:
                return True
        raw = (
            getattr(response_or_text, "body", None)
            or getattr(response_or_text, "html_content", "")
            or str(response_or_text)
        )
        return FLIGHT_MARKER in str(raw)

    return FLIGHT_MARKER in str(response_or_text)


def _to_adaptor(response: object) -> Adaptor:
    """Convert an arbitrary response or string into a Scrapling Adaptor."""
    if isinstance(response, Adaptor):
        return response
    if isinstance(response, str):
        return Adaptor(response)
    if hasattr(response, "text") and isinstance(response.text, str):
        return Adaptor(response.text)
    if hasattr(response, "body"):
        body = response.body
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return Adaptor(str(body))
    return Adaptor(str(response))


def extract_state_candidates(
    response: object,
    *,
    on_decode_error: Callable[[Exception, str, int], None] | None = None,
) -> list[StateCandidate]:
    """Discover and extract embedded JSON/state candidates from an HTML response.

    Extraction hierarchy:
    1. Explicit JSON scripts (<script type="application/json">, <script id="__NEXT_DATA__">)
    2. JavaScript global variable assignments (window.__INITIAL_STATE__, etc.)
       via JSONDecoder.raw_decode()
    3. Detects and safely ignores Next.js Flight data (self.__next_f.push)

    Malformed candidates are skipped safely without interrupting discovery.
    Returns list of StateCandidate instances ordered by discovery.
    """
    page = _to_adaptor(response)
    scripts = page.css("script")
    candidates: list[StateCandidate] = []
    decoder = json.JSONDecoder()

    # Fallback for raw text fragments without <script> tags
    if not scripts:
        raw_text = response if isinstance(response, str) else getattr(response, "text", "")
        if isinstance(raw_text, str) and raw_text.strip():
            # Check if raw text is pure JSON
            try:
                data = json.loads(raw_text.strip())
                return [StateCandidate(source="raw_json", payload=data, script_index=0)]
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
                if on_decode_error:
                    on_decode_error(exc, "raw_json", 0)

            # Check for window assignments in raw text
            seen_spans: set[int] = set()
            for marker in KNOWN_STATE_MARKERS:
                if marker in raw_text:
                    marker_pos = raw_text.find(marker)
                    while marker_pos != -1:
                        eq_pos = raw_text.find("=", marker_pos + len(marker))
                        if eq_pos == -1:
                            break
                        if raw_text[marker_pos + len(marker) : eq_pos].strip() != "":
                            marker_pos = raw_text.find(marker, marker_pos + 1)
                            continue

                        brace_pos = raw_text.find("{", eq_pos + 1)
                        bracket_pos = raw_text.find("[", eq_pos + 1)
                        pos_list = [p for p in (brace_pos, bracket_pos) if p != -1]
                        if not pos_list:
                            marker_pos = raw_text.find(marker, eq_pos + 1)
                            continue

                        start_pos = min(pos_list)
                        if raw_text[eq_pos + 1 : start_pos].strip() != "":
                            marker_pos = raw_text.find(marker, eq_pos + 1)
                            continue

                        if start_pos not in seen_spans:
                            try:
                                payload, _ = decoder.raw_decode(raw_text, start_pos)
                                seen_spans.add(start_pos)
                                candidates.append(
                                    StateCandidate(source=marker, payload=payload, script_index=0)
                                )
                            except (
                                json.JSONDecodeError,
                                UnicodeDecodeError,
                                TypeError,
                                ValueError,
                            ) as exc:
                                if on_decode_error:
                                    on_decode_error(exc, marker, 0)
                        marker_pos = raw_text.find(marker, eq_pos + 1)
        return candidates

    for script_idx, script in enumerate(scripts):
        attrib = getattr(script, "attrib", {}) or {}
        script_type = attrib.get("type", "").strip().lower()
        script_id = attrib.get("id", "").strip()
        text = (script.text or "").strip()

        if not text:
            continue

        # 1. Check explicit JSON scripts
        if script_id == "__NEXT_DATA__" or script_type == "application/json":
            try:
                payload = json.loads(text)
                source = script_id if script_id else (script_type or "application/json")
                candidates.append(
                    StateCandidate(source=source, payload=payload, script_index=script_idx)
                )
                continue
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
                logger.debug(
                    "Failed to decode application/json script at index %d: %s", script_idx, exc
                )
                if on_decode_error:
                    on_decode_error(
                        exc, script_id if script_id else (script_type or "application/json"), script_idx
                    )
                continue

        # 2. Next.js Flight marker check: skip blind decoding
        if FLIGHT_MARKER in text:
            logger.debug("Next.js Flight data marker detected in script index %d", script_idx)
            continue

        # 3. JavaScript Global Window State Assignments
        seen_spans_in_script: set[int] = set()
        for marker in KNOWN_STATE_MARKERS:
            if marker not in text:
                continue

            marker_pos = text.find(marker)
            while marker_pos != -1:
                eq_pos = text.find("=", marker_pos + len(marker))
                if eq_pos == -1:
                    break

                if text[marker_pos + len(marker) : eq_pos].strip() != "":
                    marker_pos = text.find(marker, marker_pos + 1)
                    continue

                brace_pos = text.find("{", eq_pos + 1)
                bracket_pos = text.find("[", eq_pos + 1)
                pos_list = [p for p in (brace_pos, bracket_pos) if p != -1]
                if not pos_list:
                    marker_pos = text.find(marker, eq_pos + 1)
                    continue

                start_pos = min(pos_list)
                if text[eq_pos + 1 : start_pos].strip() != "":
                    marker_pos = text.find(marker, eq_pos + 1)
                    continue

                if start_pos not in seen_spans_in_script:
                    try:
                        payload, _ = decoder.raw_decode(text, start_pos)
                        seen_spans_in_script.add(start_pos)
                        candidates.append(
                            StateCandidate(
                                source=marker,
                                payload=payload,
                                script_index=script_idx,
                            )
                        )
                    except (
                        json.JSONDecodeError,
                        UnicodeDecodeError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        logger.debug(
                            "Failed raw_decode for marker %s at script %d: %s",
                            marker,
                            script_idx,
                            exc,
                        )
                        if on_decode_error:
                            on_decode_error(exc, marker, script_idx)

                marker_pos = text.find(marker, eq_pos + 1)

    return candidates


@dataclass(frozen=True)
class StateListingResult:
    """Structured extraction result from embedded state listing."""

    product_urls: tuple[str, ...]
    current_page: int | None
    total_pages: int | None
    total_products: int | None
    has_next_page: bool | None
    source: str = "tokopedia_adapter"


_KNOWN_PATH_CHAINS: tuple[tuple[str, ...], ...] = (
    ("props", "pageProps", "initialState", "searchProduct", "data"),
    ("props", "pageProps", "initialState", "displaySearchQuery", "data"),
    ("props", "pageProps", "initialState", "ace_search_product", "data"),
    ("props", "pageProps", "initialState", "search_product", "data"),
    ("props", "pageProps", "searchProduct", "data"),
    ("props", "pageProps", "displaySearchQuery", "data"),
    ("props", "pageProps", "ace_search_product", "data"),
    ("props", "pageProps", "search_product", "data"),
    ("props", "pageProps", "data"),
    ("displaySearchQuery", "data"),
    ("searchProduct", "data"),
    ("ace_search_product", "data"),
    ("search_product", "data"),
    ("ace_search", "data"),
)


def _unwrap_payload(payload_or_candidate: object) -> object:
    if isinstance(payload_or_candidate, StateCandidate):
        return payload_or_candidate.payload
    return payload_or_candidate


def _safe_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        val_str = value.strip().replace(",", "").replace(".", "")
        if val_str.isdigit():
            try:
                return int(val_str)
            except ValueError:
                return None
    return None


def _safe_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        val_str = value.strip().lower()
        if val_str in ("true", "1", "yes"):
            return True
        if val_str in ("false", "0", "no"):
            return False
    return None


def _find_tokopedia_listing_container(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None

    # Check known hierarchical path chains
    for chain in _KNOWN_PATH_CHAINS:
        curr: object = payload
        matched = True
        for key in chain:
            if isinstance(curr, dict) and key in curr:
                curr = curr[key]
            else:
                matched = False
                break
        if (
            matched
            and isinstance(curr, dict)
            and "products" in curr
            and isinstance(curr["products"], (list, tuple))
        ):
            return curr

    # Direct container check if payload itself has products
    if "products" in payload and isinstance(payload["products"], (list, tuple)):
        return payload

    if "data" in payload and isinstance(payload["data"], dict):
        data_dict = payload["data"]
        if "products" in data_dict and isinstance(data_dict["products"], (list, tuple)):
            return data_dict

    # Check shallow top-level dict keys for known Tokopedia listing sections
    tokopedia_section_keys = (
        "searchProduct",
        "displaySearchQuery",
        "ace_search_product",
        "search_product",
        "ace_search",
    )
    for section_key in tokopedia_section_keys:
        if section_key in payload and isinstance(payload[section_key], dict):
            sec = payload[section_key]
            if isinstance(sec.get("data"), dict) and isinstance(
                sec["data"].get("products"), (list, tuple)
            ):
                return sec["data"]
            if isinstance(sec.get("products"), (list, tuple)):
                return sec

    return None


def _get_first_present(obj: dict[str, object], keys: tuple[str, ...]) -> object | None:
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None


def _extract_from_container(
    container: dict[str, object], source: str = "tokopedia_adapter"
) -> StateListingResult:
    import math

    raw_products = container.get("products", [])
    if not isinstance(raw_products, (list, tuple)):
        raw_products = []

    urls: list[str] = []
    seen: set[str] = set()

    for item in raw_products:
        if not isinstance(item, dict):
            continue

        raw_url = _get_first_present(
            item, ("url", "applink", "canonicalUrl", "desktopUrl", "link", "productUrl")
        )
        if not isinstance(raw_url, str):
            continue

        clean_url = raw_url.strip()
        if not clean_url:
            continue

        # Clean URL fragment
        clean_url = clean_url.split("#")[0]

        # Handle relative URL path
        if clean_url.startswith("/"):
            clean_url = f"https://www.tokopedia.com{clean_url}"

        if clean_url not in seen:
            seen.add(clean_url)
            urls.append(clean_url)

    # Extract pagination
    pagination_obj = container.get("pagination")
    if not isinstance(pagination_obj, dict):
        pagination_obj = container

    current_page = _safe_int(
        _get_first_present(
            pagination_obj,
            ("currentPage", "page", "current_page", "pageNumber", "currentPageNumber"),
        )
    )
    total_pages = _safe_int(
        _get_first_present(
            pagination_obj,
            ("totalPages", "total_pages", "pageCount", "maxPage", "totalPage"),
        )
    )
    total_products = _safe_int(
        _get_first_present(
            pagination_obj,
            (
                "totalData",
                "total_data",
                "totalProducts",
                "total_products",
                "totalCount",
                "count",
                "total",
            ),
        )
    )
    has_next_page = _safe_bool(
        _get_first_present(
            pagination_obj,
            ("hasNextPage", "has_next_page", "hasNext", "has_more", "hasMore"),
        )
    )

    # Infer total_pages if pageSize exists and total_pages is missing
    if total_pages is None and total_products is not None:
        page_size = _safe_int(
            _get_first_present(
                pagination_obj,
                ("pageSize", "page_size", "perPage", "rowsPerPage", "limit"),
            )
        )
        if page_size and page_size > 0:
            total_pages = math.ceil(total_products / page_size)

    # Infer has_next_page if still None
    if has_next_page is None and current_page is not None and total_pages is not None:
        has_next_page = current_page < total_pages

    return StateListingResult(
        product_urls=tuple(urls),
        current_page=current_page,
        total_pages=total_pages,
        total_products=total_products,
        has_next_page=has_next_page,
        source=source,
    )


class TokopediaListingStateAdapter:
    """Dedicated state adapter for Tokopedia listing and search page state."""

    def supports(self, payload: object) -> bool:
        """Check if candidate JSON payload contains supported Tokopedia listing state."""
        unwrapped = _unwrap_payload(payload)
        return _find_tokopedia_listing_container(unwrapped) is not None

    def extract(self, candidate: StateCandidate | object) -> StateListingResult:
        """Extract product URLs and pagination metadata from a Tokopedia state candidate.

        Accepts a StateCandidate or a raw dict payload.
        Raises ValueError if the payload does not contain a supported Tokopedia listing state.
        """
        unwrapped = _unwrap_payload(candidate)
        container = _find_tokopedia_listing_container(unwrapped)
        if container is None:
            raise ValueError(
                "Payload does not match supported Tokopedia listing state structure"
            )

        return _extract_from_container(container)


# ---------------------------------------------------------------------------
# Generic Recovery and Candidate Scoring
# ---------------------------------------------------------------------------

_GENERIC_PRODUCT_URL_KEYS: tuple[str, ...] = (
    "url",
    "productUrl",
    "product_url",
    "link",
    "desktopUrl",
    "mobileUrl",
    "applink",
    "canonicalUrl",
)

_GENERIC_PRODUCT_EVIDENCE_KEYS: frozenset[str] = frozenset({
    "id",
    "productId",
    "product_id",
    "pId",
    "name",
    "title",
    "productName",
    "product_name",
    "price",
    "priceInt",
    "price_int",
    "priceRange",
    "seller",
    "shop",
    "shopName",
    "shop_name",
    "sellerName",
    "seller_name",
    "rating",
    "ratingAverage",
    "rating_average",
    "reviewCount",
    "countReview",
    "count_review",
})

_GENERIC_NOISE_TYPES: frozenset[str] = frozenset({
    "banner",
    "promo_banner",
    "promo",
    "campaign_banner",
    "avatar",
    "profile_avatar",
    "shop_avatar",
    "carousel_banner",
})


def walk_json(
    value: object,
    *,
    max_depth: int = 20,
    _current_depth: int = 0,
    _seen: set[int] | None = None,
) -> Iterator[object]:
    """Recursively yield all nodes in a JSON tree up to max_depth.

    Handles nested dicts, lists, and primitives with cycle prevention
    and bounded recursion depth.
    """
    if isinstance(value, StateCandidate):
        value = value.payload

    yield value

    if _current_depth >= max_depth:
        return

    if _seen is None:
        _seen = set()

    if isinstance(value, Mapping):
        val_id = id(value)
        if val_id in _seen:
            return
        _seen.add(val_id)
        for v in value.values():
            yield from walk_json(
                v,
                max_depth=max_depth,
                _current_depth=_current_depth + 1,
                _seen=_seen,
            )
    elif isinstance(value, (list, tuple)):
        val_id = id(value)
        if val_id in _seen:
            return
        _seen.add(val_id)
        for item in value:
            yield from walk_json(
                item,
                max_depth=max_depth,
                _current_depth=_current_depth + 1,
                _seen=_seen,
            )


def _extract_product_url_from_record(value: Mapping[str, object]) -> str | None:
    for k in _GENERIC_PRODUCT_URL_KEYS:
        if k in value:
            raw_url = value[k]
            if isinstance(raw_url, str) and raw_url.strip():
                clean_url = raw_url.strip().split("#")[0]
                if clean_url.startswith("/"):
                    clean_url = f"https://www.tokopedia.com{clean_url}"
                if is_tokopedia_product_url(clean_url):
                    return clean_url
    return None


def looks_like_product_record(value: Mapping[str, object]) -> bool:
    """Determine whether a JSON dictionary represents a valid product listing record.

    Validation requirements:
    1. Must be a mapping/dict.
    2. Must contain a candidate URL key ('url', 'productUrl', 'product_url', 'link',
       'desktopUrl', 'mobileUrl', etc.) that passes `is_tokopedia_product_url`.
    3. Must contain at least one product identity evidence key ('id', 'productId',
       'product_id', 'name', 'title', 'price', 'priceInt', 'seller', 'shop', etc.)
       with a non-empty value.
    4. Must not be classified as explicit non-product noise (banners, avatars, etc.).
    """
    if not isinstance(value, Mapping):
        return False

    # Check for explicit noise type indicators
    val_type = str(value.get("type", "")).lower()
    if val_type in _GENERIC_NOISE_TYPES:
        return False
    val_comp_type = str(
        value.get("component_type", "") or value.get("componentType", "")
    ).lower()
    if val_comp_type in _GENERIC_NOISE_TYPES:
        return False

    # 1. URL key requirement
    valid_url = _extract_product_url_from_record(value)
    if not valid_url:
        return False

    # 2. Product identity evidence requirement
    has_evidence = False
    for k in _GENERIC_PRODUCT_EVIDENCE_KEYS:
        if k in value:
            val = value[k]
            if val is not None and val != "":
                has_evidence = True
                break

    return has_evidence


@dataclass(frozen=True)
class CandidateScore:
    """Scored state candidate evaluating product count and pagination metadata."""

    candidate: StateCandidate
    product_count: int
    has_pagination: bool
    product_urls: tuple[str, ...]
    current_page: int | None = None
    total_pages: int | None = None
    total_products: int | None = None
    has_next_page: bool | None = None

    def to_listing_result(self, source: str = "generic_recovery") -> StateListingResult:
        """Convert scored candidate into a StateListingResult."""
        return StateListingResult(
            product_urls=self.product_urls,
            current_page=self.current_page,
            total_pages=self.total_pages,
            total_products=self.total_products,
            has_next_page=self.has_next_page,
            source=source,
        )


def score_candidate(candidate: StateCandidate | object) -> CandidateScore:
    """Evaluate and score a state candidate by discovering products and pagination signals."""
    unwrapped = _unwrap_payload(candidate)
    if isinstance(candidate, StateCandidate):
        state_candidate = candidate
    else:
        state_candidate = StateCandidate(source="generic", payload=unwrapped, script_index=0)

    discovered_urls: list[str] = []
    seen_urls: set[str] = set()

    current_page: int | None = None
    total_pages: int | None = None
    total_products: int | None = None
    has_next_page: bool | None = None
    page_size: int | None = None

    for node in walk_json(unwrapped, max_depth=20):
        if isinstance(node, Mapping):
            if looks_like_product_record(node):
                url = _extract_product_url_from_record(node)
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    discovered_urls.append(url)

            # Check for pagination signals
            if current_page is None:
                current_page = _safe_int(
                    _get_first_present(
                        dict(node),
                        ("currentPage", "page", "current_page", "pageNumber", "currentPageNumber"),
                    )
                )
            if total_pages is None:
                total_pages = _safe_int(
                    _get_first_present(
                        dict(node),
                        ("totalPages", "total_pages", "pageCount", "maxPage", "totalPage"),
                    )
                )
            if total_products is None:
                total_products = _safe_int(
                    _get_first_present(
                        dict(node),
                        (
                            "totalData",
                            "total_data",
                            "totalProducts",
                            "total_products",
                            "totalCount",
                            "count",
                            "total",
                        ),
                    )
                )
            if has_next_page is None:
                has_next_page = _safe_bool(
                    _get_first_present(
                        dict(node),
                        ("hasNextPage", "has_next_page", "hasNext", "has_more", "hasMore"),
                    )
                )
            if page_size is None:
                page_size = _safe_int(
                    _get_first_present(
                        dict(node),
                        ("pageSize", "page_size", "perPage", "rowsPerPage", "limit"),
                    )
                )

    if total_pages is None and total_products is not None and page_size and page_size > 0:
        total_pages = math.ceil(total_products / page_size)

    if has_next_page is None and current_page is not None and total_pages is not None:
        has_next_page = current_page < total_pages

    has_pagination = any(
        x is not None for x in (current_page, total_pages, total_products, has_next_page)
    )

    return CandidateScore(
        candidate=state_candidate,
        product_count=len(discovered_urls),
        has_pagination=has_pagination,
        product_urls=tuple(discovered_urls),
        current_page=current_page,
        total_pages=total_pages,
        total_products=total_products,
        has_next_page=has_next_page,
    )


def score_candidates(
    candidates: Sequence[StateCandidate] | Sequence[object],
) -> list[CandidateScore]:
    """Score and rank multiple state candidates.

    Candidates are ranked primarily by valid product record count (descending),
    with presence of pagination metadata as a secondary tie-breaker.
    """
    scores = [
        score_candidate(c if isinstance(c, StateCandidate) else StateCandidate("generic", c, idx))
        for idx, c in enumerate(candidates)
    ]
    return sorted(
        scores,
        key=lambda s: (s.product_count, 1 if s.has_pagination else 0),
        reverse=True,
    )


def extract_generic_state(
    candidate_or_candidates: Sequence[StateCandidate] | StateCandidate | object,
) -> StateListingResult:
    """Extract listing results via generic recursive traversal and candidate scoring.

    If given a sequence of candidates, evaluates all and selects the top candidate.
    Returns StateListingResult with source='generic_recovery'.
    """
    if isinstance(candidate_or_candidates, (list, tuple)):
        if not candidate_or_candidates:
            return StateListingResult(
                product_urls=(),
                current_page=None,
                total_pages=None,
                total_products=None,
                has_next_page=None,
                source="generic_recovery",
            )
        ranked = score_candidates(candidate_or_candidates)
        return ranked[0].to_listing_result(source="generic_recovery")

    cand = (
        candidate_or_candidates
        if isinstance(candidate_or_candidates, StateCandidate)
        else StateCandidate("generic", candidate_or_candidates, 0)
    )
    score = score_candidate(cand)
    return score.to_listing_result(source="generic_recovery")
