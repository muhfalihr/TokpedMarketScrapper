import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tokped_market_scrapper.storage import SQLiteStore


@dataclass(frozen=True)
class ReadinessDataset:
    """Read-only container holding DataFrames and raw payload mappings for ML readiness audit."""

    products: pd.DataFrame
    provenance: pd.DataFrame
    discoveries: pd.DataFrame
    raw_by_listing_key: Mapping[str, dict[str, Any]]


def load_readiness_dataset(
    *,
    run_id: str,
    store: SQLiteStore,
    raw_jsonl_path: Path | str | None = None,
) -> ReadinessDataset:
    """Load products, feature provenance, product discoveries, and raw JSONL into a ReadinessDataset snapshot.

    Reads SQLite tables via store read methods and builds DataFrames without mutating underlying data.
    If raw_jsonl_path is specified and exists, parses raw products.jsonl indexed by listing_key.
    """
    products_data = store.read_products_for_run(run_id)
    if not products_data:
        products_data = store.read_products_for_run(None)

    provenance_data = store.read_feature_provenance_for_run(run_id)
    if not provenance_data:
        provenance_data = store.read_feature_provenance_for_run(None)

    discoveries_data = store.read_discoveries_for_run(run_id)
    if not discoveries_data:
        discoveries_data = store.read_discoveries_for_run(None)

    products_df = pd.DataFrame(products_data)
    provenance_df = pd.DataFrame(provenance_data)
    discoveries_df = pd.DataFrame(discoveries_data)

    raw_by_listing_key: dict[str, dict[str, Any]] = {}

    if raw_jsonl_path is not None:
        target_path = Path(raw_jsonl_path)
        if target_path.is_dir():
            candidates = [
                target_path / "products.jsonl",
                target_path / run_id / "products.jsonl",
                target_path / "raw" / run_id / "products.jsonl",
            ]
            found = next((c for c in candidates if c.is_file()), None)
            if found is None:
                found = next(iter(target_path.rglob("products.jsonl")), None)
            target_path = found

        if target_path is not None and target_path.is_file():
            with open(target_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        try:
                            record = json.loads(line_str)
                            if isinstance(record, dict):
                                prod = record.get("product") if isinstance(record.get("product"), dict) else record
                                key = prod.get("listing_key") or prod.get("canonical_url") or prod.get("product_id")
                                if key:
                                    raw_by_listing_key[str(key)] = record
                        except (json.JSONDecodeError, ValueError):
                            pass

    return ReadinessDataset(
        products=products_df,
        provenance=provenance_df,
        discoveries=discoveries_df,
        raw_by_listing_key=raw_by_listing_key,
    )
