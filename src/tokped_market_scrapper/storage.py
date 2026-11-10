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

from tokped_market_scrapper.models import FeatureProvenance, NormalizedProduct, RawProduct
from tokped_market_scrapper.normalization import (
    normalize_count,
    normalize_idr,
    normalize_percent,
    normalize_rating,
)
from tokped_market_scrapper.url_utils import canonicalize_product_url, make_listing_key

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

CREATE TABLE IF NOT EXISTS product_discoveries (
    crawl_run_id TEXT NOT NULL,
    listing_key TEXT NOT NULL,
    source_query TEXT NOT NULL,
    seed_kind TEXT NOT NULL,
    search_page INTEGER NOT NULL,
    search_start INTEGER NOT NULL,
    search_rows INTEGER NOT NULL,
    search_rank INTEGER NOT NULL,
    category_sc TEXT NOT NULL,
    sort_code TEXT NOT NULL,
    observed_total_data INTEGER,
    product_name TEXT,
    category_breadcrumb TEXT,
    discovered_at TEXT NOT NULL,
    PRIMARY KEY (
        crawl_run_id,
        listing_key,
        source_query,
        search_page
    )
);

CREATE TABLE IF NOT EXISTS feature_provenance (
    crawl_run_id TEXT NOT NULL,
    listing_key TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    source_layer TEXT NOT NULL,
    source_field TEXT NOT NULL,
    value_kind TEXT NOT NULL DEFAULT 'numeric',
    raw_value_json TEXT,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (crawl_run_id, listing_key, feature_name)
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
        try:
            self._conn.execute("ALTER TABLE product_discoveries ADD COLUMN product_name TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self._conn.execute("ALTER TABLE product_discoveries ADD COLUMN category_breadcrumb TEXT")
        except sqlite3.OperationalError:
            pass

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

    def record_discovery(
        self,
        *,
        crawl_run_id: str,
        listing_key: str,
        source_query: str,
        seed_kind: str,
        search_page: int,
        search_start: int,
        search_rows: int,
        search_rank: int,
        category_sc: str,
        sort_code: str,
        observed_total_data: int | None = None,
        product_name: str | None = None,
        category_breadcrumb: str | None = None,
        discovered_at: str | None = None,
    ) -> None:
        """Record search discovery provenance.

        Uses INSERT OR IGNORE to prevent duplicate entries for identical
        crawl_run_id, listing_key, source_query, and search_page.
        """
        if discovered_at is None:
            discovered_at = datetime.now(UTC).isoformat()

        self._conn.execute(
            """\
            INSERT OR IGNORE INTO product_discoveries (
                crawl_run_id,
                listing_key,
                source_query,
                seed_kind,
                search_page,
                search_start,
                search_rows,
                search_rank,
                category_sc,
                sort_code,
                observed_total_data,
                product_name,
                category_breadcrumb,
                discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                crawl_run_id,
                listing_key,
                source_query,
                seed_kind,
                search_page,
                search_start,
                search_rows,
                search_rank,
                category_sc,
                sort_code,
                observed_total_data,
                product_name,
                category_breadcrumb,
                discovered_at,
            ),
        )
        self._conn.commit()

    def count_discoveries(
        self, listing_key: str | None = None, crawl_run_id: str | None = None
    ) -> int:
        """Count discovery records, optionally filtered by listing_key and/or crawl_run_id."""
        query = "SELECT COUNT(*) FROM product_discoveries"
        params: list[str] = []
        where_clauses: list[str] = []

        if listing_key is not None:
            where_clauses.append("listing_key = ?")
            params.append(listing_key)
        if crawl_run_id is not None:
            where_clauses.append("crawl_run_id = ?")
            params.append(crawl_run_id)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        row = self._conn.execute(query, params).fetchone()
        return row[0] if row else 0

    def export_discoveries_csv(self, crawl_run_id: str, output_path: str | Path) -> Path:
        """Export product discoveries for a given crawl_run_id to a CSV file."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        columns = [
            "crawl_run_id",
            "listing_key",
            "source_query",
            "seed_kind",
            "search_page",
            "search_start",
            "search_rows",
            "search_rank",
            "category_sc",
            "sort_code",
            "observed_total_data",
            "product_name",
            "category_breadcrumb",
            "discovered_at",
        ]

        rows = self._conn.execute(
            """\
            SELECT crawl_run_id, listing_key, source_query, seed_kind, search_page,
                   search_start, search_rows, search_rank, category_sc, sort_code,
                   observed_total_data, product_name, category_breadcrumb, discovered_at
            FROM product_discoveries
            WHERE crawl_run_id = ?
            """,
            (crawl_run_id,),
        ).fetchall()

        df = pd.DataFrame(rows, columns=columns)
        df.to_csv(out, index=False)
        return out

    def get_discoveries(self, run_id: str | None = None) -> list[dict]:
        """Retrieve discovery records as a list of dicts."""
        if run_id:
            rows = self._conn.execute(
                """\
                SELECT crawl_run_id, listing_key, source_query, seed_kind, search_page,
                       search_start, search_rows, search_rank, category_sc, sort_code,
                       observed_total_data, product_name, category_breadcrumb, discovered_at
                FROM product_discoveries
                WHERE crawl_run_id = ?
                """,
                (run_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """\
                SELECT crawl_run_id, listing_key, source_query, seed_kind, search_page,
                       search_start, search_rows, search_rank, category_sc, sort_code,
                       observed_total_data, product_name, category_breadcrumb, discovered_at
                FROM product_discoveries
                """
            ).fetchall()

        cols = [
            "crawl_run_id",
            "listing_key",
            "source_query",
            "seed_kind",
            "search_page",
            "search_start",
            "search_rows",
            "search_rank",
            "category_sc",
            "sort_code",
            "observed_total_data",
            "product_name",
            "category_breadcrumb",
            "discovered_at",
        ]
        return [dict(zip(cols, r)) for r in rows]

    def save_feature_provenance(
        self,
        run_id: str,
        listing_key: str,
        feature_name: str,
        source_layer: str,
        source_field: str,
        raw_value: Any = None,
        value_kind: str = "numeric",
        observed_at: str | None = None,
    ) -> None:
        """Save or replace a field-level feature provenance record."""
        if observed_at is None:
            observed_at = datetime.now(UTC).isoformat()

        raw_value_json = json.dumps(raw_value) if raw_value is not None else None

        self._conn.execute(
            """\
            INSERT OR REPLACE INTO feature_provenance (
                crawl_run_id,
                listing_key,
                feature_name,
                source_layer,
                source_field,
                value_kind,
                raw_value_json,
                observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                listing_key,
                feature_name,
                source_layer,
                source_field,
                value_kind,
                raw_value_json,
                observed_at,
            ),
        )
        self._conn.commit()

    def get_feature_provenance(
        self, run_id: str, listing_key: str, feature_name: str
    ) -> FeatureProvenance | None:
        """Fetch single provenance record."""
        row = self._conn.execute(
            """\
            SELECT crawl_run_id, listing_key, feature_name, source_layer, source_field, value_kind, raw_value_json, observed_at
            FROM feature_provenance
            WHERE crawl_run_id = ? AND listing_key = ? AND feature_name = ?
            """,
            (run_id, listing_key, feature_name),
        ).fetchone()

        if not row:
            return None

        return FeatureProvenance(
            crawl_run_id=row[0],
            listing_key=row[1],
            feature_name=row[2],
            source_layer=row[3],
            source_field=row[4],
            value_kind=row[5],
            raw_value_json=row[6],
            observed_at=row[7],
        )

    def get_all_feature_provenance(self, run_id: str) -> list[FeatureProvenance]:
        """Fetch all provenance records for a run."""
        rows = self._conn.execute(
            """\
            SELECT crawl_run_id, listing_key, feature_name, source_layer, source_field, value_kind, raw_value_json, observed_at
            FROM feature_provenance
            WHERE crawl_run_id = ?
            """,
            (run_id,),
        ).fetchall()

        return [
            FeatureProvenance(
                crawl_run_id=row[0],
                listing_key=row[1],
                feature_name=row[2],
                source_layer=row[3],
                source_field=row[4],
                value_kind=row[5],
                raw_value_json=row[6],
                observed_at=row[7],
            )
            for row in rows
        ]

    def read_products_for_run(self, run_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve products for a run (or all if run_id is None) as a list of dicts."""
        if run_id:
            rows = self._conn.execute(
                "SELECT payload_json FROM products WHERE crawl_run_id = ?", (run_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT payload_json FROM products").fetchall()
        return [json.loads(row[0]) for row in rows]

    def read_feature_provenance_for_run(self, run_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve feature provenance for a run (or all if run_id is None) as a list of dicts."""
        cols = [
            "crawl_run_id",
            "listing_key",
            "feature_name",
            "source_layer",
            "source_field",
            "value_kind",
            "raw_value_json",
            "observed_at",
        ]
        if run_id:
            rows = self._conn.execute(
                """\
                SELECT crawl_run_id, listing_key, feature_name, source_layer, source_field, value_kind, raw_value_json, observed_at
                FROM feature_provenance
                WHERE crawl_run_id = ?
                """,
                (run_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """\
                SELECT crawl_run_id, listing_key, feature_name, source_layer, source_field, value_kind, raw_value_json, observed_at
                FROM feature_provenance
                """
            ).fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def read_discoveries_for_run(self, run_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve discovery records for a run (or all if run_id is None) as a list of dicts."""
        return self.get_discoveries(run_id=run_id)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()




MarketStorage = SQLiteStore

