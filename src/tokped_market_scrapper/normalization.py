import re

_SUFFIXES: dict[str, int] = {
    "rb": 1_000,
    "k": 1_000,
    "jt": 1_000_000,
    "m": 1_000_000,
}


def normalize_count(value: str | int | None) -> int | None:
    """Normalize raw marketplace count strings (e.g., '1,2rb+ terjual') to integers."""
    if value is None:
        return None
    if isinstance(value, int):
        return value

    text = str(value).strip().lower()
    if not text or text in {"-", "null", "none", "n/a"}:
        return None

    match = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-z]+)?", text)
    if not match:
        return None

    num_str, suffix = match.groups()
    if suffix and suffix in _SUFFIXES:
        num_clean = num_str.replace(",", ".")
        try:
            return round(float(num_clean) * _SUFFIXES[suffix])
        except ValueError:
            return None

    num_clean = num_str.replace(".", "").replace(",", "")
    try:
        return int(num_clean)
    except ValueError:
        return None


def normalize_idr(value: str | int | None) -> int | None:
    """Normalize Indonesian Rupiah currency strings (e.g., 'Rp12.499.000') to integer."""
    if value is None:
        return None
    if isinstance(value, int):
        return value

    text = str(value).strip().lower()
    if not text or text in {"-", "null", "none", "n/a"}:
        return None

    text = re.sub(r",\d{1,2}$", "", text)
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


def normalize_percent(value: str | float | None) -> float | None:
    """Normalize percentage strings (e.g., '15%') to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    if not text or text in {"-", "null", "none", "n/a"}:
        return None

    text = text.replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def normalize_rating(value: str | float | None) -> float | None:
    """Normalize product rating strings (e.g., '4,9') to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    if not text or text in {"-", "null", "none", "n/a"}:
        return None

    text = text.replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None
