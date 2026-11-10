"""SQLite storage for the multi-category catalog pipeline.

Persists search-layer products, keyword hits (for n_keyword_hits), and
PDP enrichment results with checkpoint/resume semantics, then exports a
CSV matching the reference dataset schema (tokopedia_products_v2.csv).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from laptop_market_scraper.catalog.models import (
    CRAWLER_VERSION,
    SORT_LABELS,
    CatalogProduct,
    EnrichmentResult,
)

WIB = timezone(timedelta(hours=7))

EXPORT_COLUMNS: tuple[str, ...] = (
    "product_id",
    "name",
    "price",
    "rating",
    "review_count",
    "sold",
    "sold_label",
    "category",
    "category_breadcrumb",
    "category_id",
    "url",
    "shop_name",
    "shop_city",
    "is_official",
    "source_keyword",
    "sort",
    "discount_pct",
    "original_price_fmt",
    "original_price",
    "crawl_timestamp",
    "page_number",
    "rank_in_page",
    "shop_id",
    "shop_tier",
    "is_ad",
    "n_keyword_hits",
    "crawler_version",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_products (
    crawl_run_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (crawl_run_id, product_id)
);

CREATE TABLE IF NOT EXISTS catalog_hits (
    crawl_run_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    page INTEGER NOT NULL,
    rank_in_page INTEGER NOT NULL,
    hit_at TEXT NOT NULL,
    PRIMARY KEY (crawl_run_id, product_id, keyword, page)
);

CREATE TABLE IF NOT EXISTS catalog_enrichment (
    crawl_run_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    status TEXT NOT NULL,
    review_count INTEGER,
    sold INTEGER,
    rating REAL,
    category_id TEXT,
    error TEXT,
    enriched_at TEXT NOT NULL,
    PRIMARY KEY (crawl_run_id, product_id)
);
"""

_ENRICHMENT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_enrichment_status
ON catalog_enrichment (crawl_run_id, status);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class CatalogStore:
    """SQLite-backed store for catalog products, hits, and enrichment results."""

    def __init__(self, db_path: str | Path, data_dir: str | Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.data_dir = Path(data_dir) if data_dir is not None else self.db_path.parent
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.execute(_ENRICHMENT_INDEX)
        self.conn.commit()

    # ---------------------------------------------------------------- products

    def save_product(self, product: CatalogProduct) -> bool:
        """Insert a catalog product; returns False when already present (dedup)."""
        try:
            self.conn.execute(
                "INSERT INTO catalog_products (crawl_run_id, product_id, payload_json) "
                "VALUES (?, ?, ?)",
                (
                    product.crawl_run_id,
                    product.product_id,
                    product.model_dump_json(),
                ),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False
        self.conn.commit()

        raw_dir = self.data_dir / "raw" / product.crawl_run_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        with open(raw_dir / "catalog_products.jsonl", "a", encoding="utf-8") as f:
            f.write(product.model_dump_json() + "\n")
        return True

    def record_hit(
        self,
        *,
        crawl_run_id: str,
        product_id: str,
        keyword: str,
        page: int,
        rank_in_page: int,
    ) -> None:
        """Record one keyword hit (deduplicated by keyword+page)."""
        self.conn.execute(
            "INSERT OR IGNORE INTO catalog_hits "
            "(crawl_run_id, product_id, keyword, page, rank_in_page, hit_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (crawl_run_id, product_id, keyword, page, rank_in_page, _now_iso()),
        )
        self.conn.commit()

    def count_products(self, crawl_run_id: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM catalog_products"
        params: tuple[Any, ...] = ()
        if crawl_run_id is not None:
            query += " WHERE crawl_run_id = ?"
            params = (crawl_run_id,)
        row = self.conn.execute(query, params).fetchone()
        return int(row[0])

    def count_hits(self, crawl_run_id: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM catalog_hits"
        params: tuple[Any, ...] = ()
        if crawl_run_id is not None:
            query += " WHERE crawl_run_id = ?"
            params = (crawl_run_id,)
        row = self.conn.execute(query, params).fetchone()
        return int(row[0])

    def list_runs(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT crawl_run_id FROM catalog_products ORDER BY crawl_run_id"
        ).fetchall()
        return [str(r[0]) for r in rows]

    # ------------------------------------------------------------- enrichment

    def pending_enrichment(
        self,
        crawl_run_id: str,
        limit: int | None = None,
        retry_failed: bool = False,
    ) -> list[tuple[str, str]]:
        """Return (product_id, product_url) pairs not yet enriched.

        Args:
            crawl_run_id: Run to select products from.
            limit: Optional cap on returned pairs.
            retry_failed: When True, also re-select previously failed attempts.
        """
        query = (
            "SELECT p.product_id, json_extract(p.payload_json, '$.url') AS url "
            "FROM catalog_products p "
            "LEFT JOIN catalog_enrichment e "
            "ON e.crawl_run_id = p.crawl_run_id AND e.product_id = p.product_id "
            "WHERE p.crawl_run_id = ? AND e.product_id IS NULL"
        )
        if retry_failed:
            query = query.replace("e.product_id IS NULL", "(e.product_id IS NULL OR e.status = 'fail')")
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        rows = self.conn.execute(query, (crawl_run_id,)).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]

    def save_enrichment(self, result: EnrichmentResult) -> None:
        """Upsert an enrichment result (checkpoint marker)."""
        self.conn.execute(
            "INSERT INTO catalog_enrichment "
            "(crawl_run_id, product_id, status, review_count, sold, rating, category_id, error, enriched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(crawl_run_id, product_id) DO UPDATE SET "
            "status = excluded.status, review_count = excluded.review_count, "
            "sold = excluded.sold, rating = excluded.rating, "
            "category_id = excluded.category_id, error = excluded.error, "
            "enriched_at = excluded.enriched_at",
            (
                result.crawl_run_id,
                result.product_id,
                result.status,
                result.review_count,
                result.sold,
                result.rating,
                result.category_id,
                result.error,
                result.enriched_at.isoformat(),
            ),
        )
        self.conn.commit()

    def enrichment_stats(self, crawl_run_id: str) -> dict[str, int]:
        """Count enrichment outcomes per status for a run."""
        rows = self.conn.execute(
            "SELECT status, COUNT(*) FROM catalog_enrichment "
            "WHERE crawl_run_id = ? GROUP BY status",
            (crawl_run_id,),
        ).fetchall()
        stats = {str(status): int(count) for status, count in rows}
        total = self.count_products(crawl_run_id)
        stats["pending"] = total - sum(v for k, v in stats.items() if k != "pending")
        return stats

    # ------------------------------------------------------------------ export

    def export_products_csv(
        self,
        csv_path: str | Path,
        crawl_run_id: str,
        require_enrichment: bool = False,
    ) -> Path:
        """Export merged (search + enrichment) products to the reference CSV schema.

        Args:
            csv_path: Destination CSV path.
            crawl_run_id: Run to export.
            require_enrichment: When True, only export rows with a successful PDP
                enrichment. This matches the reference dataset semantics, where
                ``review_count`` and ``sold`` always come from the product page
                (un-enriched rows would otherwise carry an empty ``review_count``
                and a bucket-floor ``sold``).

        Returns:
            Resolved output path.
        """
        import pandas as pd

        out_path = Path(csv_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if require_enrichment:
            products = self.conn.execute(
                "SELECT p.payload_json FROM catalog_products p "
                "JOIN catalog_enrichment e "
                "ON e.crawl_run_id = p.crawl_run_id AND e.product_id = p.product_id "
                "WHERE p.crawl_run_id = ? AND e.status IN ('ok', 'partial')",
                (crawl_run_id,),
            ).fetchall()
        else:
            products = self.conn.execute(
                "SELECT payload_json FROM catalog_products WHERE crawl_run_id = ?",
                (crawl_run_id,),
            ).fetchall()

        hits = self.conn.execute(
            "SELECT product_id, COUNT(DISTINCT keyword) FROM catalog_hits "
            "WHERE crawl_run_id = ? GROUP BY product_id",
            (crawl_run_id,),
        ).fetchall()
        hit_counts = {str(pid): int(n) for pid, n in hits}

        enrichments = self.conn.execute(
            "SELECT product_id, status, review_count, sold, rating, category_id "
            "FROM catalog_enrichment WHERE crawl_run_id = ?",
            (crawl_run_id,),
        ).fetchall()
        enrich_by_pid = {str(r[0]): r for r in enrichments}

        records: list[dict[str, Any]] = []
        for (payload_json,) in products:
            p = json.loads(payload_json)
            enrich = enrich_by_pid.get(p["product_id"])

            review_count: int | None = None
            sold_exact: int | None = None
            rating = p.get("rating")
            category_id = p.get("category_id")
            if enrich is not None:
                _, status, e_review, e_sold, e_rating, e_cat_id = enrich
                if status in ("ok", "partial"):
                    review_count = int(e_review) if e_review is not None else None
                    sold_exact = int(e_sold) if e_sold is not None else None
                    if e_rating is not None:
                        rating = float(e_rating)
                    if e_cat_id:
                        category_id = str(e_cat_id)

            breadcrumb = p.get("category_breadcrumb")
            top_category = breadcrumb.split("/")[0] if breadcrumb else None

            discount_pct = p.get("discount_percent")
            original_price = p.get("original_price")
            if discount_pct is None and original_price and p.get("price"):
                discount_pct = round((1 - p["price"] / original_price) * 100, 1)

            scraped_at = p.get("scraped_at")
            crawl_ts = None
            if scraped_at:
                crawl_ts = datetime.fromisoformat(scraped_at).astimezone(WIB).isoformat()

            records.append(
                {
                    "product_id": p["product_id"],
                    "name": p["name"],
                    "price": p.get("price"),
                    "rating": rating,
                    "review_count": review_count,
                    "sold": sold_exact if sold_exact is not None else p.get("sold_count_floor"),
                    "sold_label": p.get("sold_label"),
                    "category": top_category,
                    "category_breadcrumb": breadcrumb,
                    "category_id": category_id,
                    "url": p.get("canonical_url") or p.get("url"),
                    "shop_name": p.get("shop_name"),
                    "shop_city": p.get("shop_city"),
                    "is_official": p.get("is_official"),
                    "source_keyword": p.get("source_keyword"),
                    "sort": SORT_LABELS.get(p.get("sort_code", "23"), p.get("sort_code")),
                    "discount_pct": discount_pct,
                    "original_price_fmt": p.get("original_price_raw"),
                    "original_price": original_price,
                    "crawl_timestamp": crawl_ts,
                    "page_number": p.get("source_page"),
                    "rank_in_page": p.get("source_rank"),
                    "shop_id": p.get("shop_id"),
                    "shop_tier": p.get("shop_tier"),
                    "is_ad": p.get("is_ad"),
                    "n_keyword_hits": hit_counts.get(p["product_id"], 1),
                    "crawler_version": CRAWLER_VERSION,
                }
            )

        df = pd.DataFrame(records, columns=list(EXPORT_COLUMNS))
        df.to_csv(out_path, index=False)
        return out_path

    def close(self) -> None:
        self.conn.close()
