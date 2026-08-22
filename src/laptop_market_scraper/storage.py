"""JSONL + SQLite persistence and processed export.

Handles deduplication via (crawl_run_id, listing_key) composite key,
raw JSONL append, rejected item tracking, and CSV/Parquet export.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from laptop_market_scraper.models import NormalizedProduct, RawProduct
from laptop_market_scraper.normalization import (
    normalize_count,
    normalize_idr,
    normalize_percent,
    normalize_rating,
)
from laptop_market_scraper.url_utils import canonicalize_product_url, make_listing_key


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS products (
    crawl_run_id TEXT NOT NULL,
    listing_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (crawl_run_id, listing_key)
);

CREATE TABLE IF NOT EXISTS rejected (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_run_id TEXT NOT NULL,
    product_url TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""

_EXPORT_COLUMNS = [
    "crawl_run_id",
    "scraped_at",
    "product_name",
    "product_url",
    "canonical_url",
    "listing_key",
    "brand",
    "category",
    "subcategory",
    "shop_name",
    "shop_location",
    "official_store",
    "price",
    "original_price",
    "discount_percent",
    "sold_count",
    "view_count",
    "review_count",
    "talk_count",
    "transaction_success",
    "transaction_reject",
    "rating",
    "source_type",
    "source_query",
    "source_url",
    "source_page",
]


def normalize_product(raw: RawProduct) -> NormalizedProduct:
    """Convert a raw scraped product into a normalized product.

    Applies IDR, count, percent, and rating normalizers.
    Raw values are never overwritten — they live on the RawProduct.
    """
    canonical = canonicalize_product_url(raw.product_url)
    key = make_listing_key(raw.product_id, canonical)

    return NormalizedProduct(
        crawl_run_id=raw.crawl_run_id,
        scraped_at=raw.scraped_at,
        product_name=raw.product_name_raw or "",
        product_url=raw.product_url,
        canonical_url=canonical,
        product_id=raw.product_id,
        listing_key=key,
        price=normalize_idr(raw.price_raw),
        original_price=normalize_idr(raw.original_price_raw),
        discount_percent=normalize_percent(raw.discount_raw),
        sold_count=normalize_count(raw.sold_count_raw),
        view_count=normalize_count(raw.view_count_raw),
        review_count=normalize_count(raw.review_count_raw),
        talk_count=normalize_count(raw.talk_count_raw),
        rating=normalize_rating(raw.rating_raw),
        brand=raw.brand,
        category=raw.category,
        subcategory=raw.subcategory,
        shop_name=raw.shop_name,
        shop_location=raw.shop_location,
        official_store=raw.official_store,
        source_type=raw.source_type,
        source_query=raw.source_query,
        source_url=raw.source_url,
        source_page=raw.source_page,
    )


class SQLiteStore:
    """Durable storage backed by SQLite with JSONL raw append."""

    def __init__(self, db_path: str | Path, data_dir: str | Path | None = None):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._data_dir = Path(data_dir) if data_dir else self._db_path.parent
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.executescript(_SCHEMA)

    def save(self, product: NormalizedProduct) -> bool:
        """Save a normalized product. Returns True if new, False if duplicate."""
        payload = product.model_dump_json()
        try:
            self._conn.execute(
                "INSERT INTO products (crawl_run_id, listing_key, payload_json) VALUES (?, ?, ?)",
                (product.crawl_run_id, product.listing_key, payload),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            return False

        # Append to raw JSONL
        run_dir = self._data_dir / "raw" / product.crawl_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        with open(run_dir / "products.jsonl", "a", encoding="utf-8") as f:
            f.write(payload + "\n")

        return True

    def save_rejected(self, raw: RawProduct, reason: str) -> None:
        """Persist a rejected product with its rejection reason."""
        payload = raw.model_dump_json()
        self._conn.execute(
            "INSERT INTO rejected (crawl_run_id, product_url, reason, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (raw.crawl_run_id, raw.product_url, reason, payload),
        )
        self._conn.commit()

        # Append to rejected JSONL
        run_dir = self._data_dir / "raw" / raw.crawl_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        with open(run_dir / "rejected.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"reason": reason, "product": json.loads(payload)}) + "\n")

    def count_products(self, run_id: str | None = None) -> int:
        """Count products, optionally filtered by run_id."""
        if run_id:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM products WHERE crawl_run_id = ?", (run_id,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM products").fetchone()
        return row[0] if row else 0

    def count_rejected(self, run_id: str | None = None) -> int:
        """Count rejected products."""
        if run_id:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM rejected WHERE crawl_run_id = ?", (run_id,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM rejected").fetchone()
        return row[0] if row else 0

    def get_all_products(self, run_id: str | None = None) -> list[NormalizedProduct]:
        """Retrieve all products, optionally filtered by run_id."""
        if run_id:
            rows = self._conn.execute(
                "SELECT payload_json FROM products WHERE crawl_run_id = ?", (run_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT payload_json FROM products").fetchall()
        return [NormalizedProduct.model_validate_json(row[0]) for row in rows]

    def export_processed(self, csv_path: str | Path, parquet_path: str | Path) -> None:
        """Export all products to CSV and Parquet files."""
        rows = self._conn.execute("SELECT payload_json FROM products").fetchall()
        records = []
        for (payload_json,) in rows:
            data = json.loads(payload_json)
            records.append(data)

        if not records:
            # Create empty files with correct columns
            df = pd.DataFrame(columns=_EXPORT_COLUMNS)
        else:
            df = pd.DataFrame(records)
            # Ensure all export columns are present
            for col in _EXPORT_COLUMNS:
                if col not in df.columns:
                    df[col] = None
            df = df[_EXPORT_COLUMNS]

        csv_out = Path(csv_path)
        parquet_out = Path(parquet_path)
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        parquet_out.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(csv_out, index=False)
        df.to_parquet(parquet_out, index=False)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
