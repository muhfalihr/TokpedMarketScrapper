"""Embedded state candidate discovery and extraction for listing pages."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from scrapling.parser import Adaptor

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
    "StateCandidate",
    "StateListingResult",
    "TokopediaListingStateAdapter",
    "decode_json_assignment",
    "detect_flight_marker",
    "extract_state_candidates",
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


def extract_state_candidates(response: object) -> list[StateCandidate]:
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
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
                pass

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
                            ):
                                pass
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
