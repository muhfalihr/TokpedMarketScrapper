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
