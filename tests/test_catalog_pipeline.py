"""Unit tests for the multi-category catalog pipeline (models, config, store, enrich)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from laptop_market_scraper.catalog.config import load_catalog_seed_config
from laptop_market_scraper.catalog.enrich import extract_pdp_metrics_from_html
from laptop_market_scraper.catalog.models import (
    CRAWLER_VERSION,
    CatalogProduct,
    CatalogSeedConfig,
    EnrichmentResult,
)
from laptop_market_scraper.catalog.store import EXPORT_COLUMNS, CatalogStore

RUN_ID = "20260101T000000Z-test0001"


def make_product(product_id: str = "111", keyword: str = "iphone", **overrides) -> CatalogProduct:
    base = {
        "crawl_run_id": RUN_ID,
        "scraped_at": datetime.now(UTC),
        "product_id": product_id,
        "name": f"Product {product_id}",
        "url": f"https://www.tokopedia.com/shop/product-{product_id}?extParam=src%3Dsearch",
        "canonical_url": f"https://www.tokopedia.com/shop/product-{product_id}",
        "price": 75_000,
        "original_price_raw": "Rp150.000",
        "original_price": 150_000,
        "discount_percent": 50.0,
        "rating": 4.9,
        "sold_label": "100+ terjual",
        "sold_count_floor": 100,
        "category_id": "3063",
        "category_name": "Handphone & Tablet",
        "category_breadcrumb": "handphone-tablet/aksesoris-handphone/hard-case-handphone",
        "shop_id": "222",
        "shop_name": "Test Shop",
        "shop_city": "Jakarta Pusat",
        "shop_tier": 2,
        "is_official": True,
        "is_ad": False,
        "source_keyword": keyword,
        "source_shop_tier_filter": 2,
        "source_page": 1,
        "source_rank": 3,
    }
    base.update(overrides)
    return CatalogProduct(**base)


# --------------------------------------------------------------------- models


def test_catalog_seed_config_task_expansion():
    cfg = CatalogSeedConfig(
        keywords=("iphone", "kulkas"),
        tiers=(2, 1),
        max_pages_per_task=2,
        rows=60,
    )
    tasks = cfg.tasks()
    assert len(tasks) == 2 * 2 * 2  # keywords x tiers x pages
    first = tasks[0]
    assert first.keyword == "iphone"
    assert first.shop_tier == 2
    assert first.page == 1
    assert first.rows == 60
    assert any(t.page == 2 for t in tasks)


def test_catalog_product_requires_provenance():
    p = make_product()
    assert p.source_keyword == "iphone"
    assert p.source_page == 1
    assert p.source_rank == 3


# --------------------------------------------------------------------- config


def test_load_catalog_seed_config(tmp_path: Path):
    cfg_file = tmp_path / "seeds.yaml"
    cfg_file.write_text(
        """
search:
  rows: 30
  category_sc: null
  sort_code: "23"
  max_pages_per_task: 1
tiers: [2, 1]
keywords:
  - iphone
  - kulkas
""",
        encoding="utf-8",
    )
    cfg = load_catalog_seed_config(cfg_file)
    assert cfg.rows == 30
    assert cfg.category_sc is None
    assert cfg.tiers == (2, 1)
    assert cfg.keywords == ("iphone", "kulkas")
    assert len(cfg.tasks()) == 4


def test_load_catalog_seed_config_rejects_empty_keywords(tmp_path: Path):
    cfg_file = tmp_path / "seeds.yaml"
    cfg_file.write_text("search:\n  rows: 60\nkeywords: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no keywords"):
        load_catalog_seed_config(cfg_file)


def test_load_catalog_seed_config_real_file():
    cfg = load_catalog_seed_config("config/catalog_seeds.yaml")
    assert len(cfg.keywords) >= 40
    assert cfg.tiers == (2, 1)
    assert cfg.category_sc is None


# ---------------------------------------------------------------------- store


@pytest.fixture()
def store(tmp_path: Path):
    s = CatalogStore(tmp_path / "catalog.db", data_dir=tmp_path)
    yield s
    s.close()


def test_store_save_product_and_dedup(store: CatalogStore, tmp_path: Path):
    p = make_product("111")
    assert store.save_product(p) is True
    assert store.save_product(make_product("111")) is False  # dedup
    assert store.count_products(RUN_ID) == 1

    jsonl = tmp_path / "raw" / RUN_ID / "catalog_products.jsonl"
    assert jsonl.exists()
    assert len(jsonl.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_store_hits_and_pending_enrichment(store: CatalogStore):
    store.save_product(make_product("111"))
    store.save_product(make_product("222"))

    store.record_hit(
        crawl_run_id=RUN_ID, product_id="111", keyword="iphone", page=1, rank_in_page=3
    )
    store.record_hit(
        crawl_run_id=RUN_ID, product_id="111", keyword="case hp", page=1, rank_in_page=7
    )
    store.record_hit(
        crawl_run_id=RUN_ID, product_id="222", keyword="kulkas", page=1, rank_in_page=1
    )
    assert store.count_hits(RUN_ID) == 3

    pending = store.pending_enrichment(RUN_ID)
    assert len(pending) == 2
    assert pending[0][0] == "111"

    store.save_enrichment(
        EnrichmentResult(
            crawl_run_id=RUN_ID,
            product_id="111",
            status="ok",
            review_count=42,
            sold=1200,
            rating=4.8,
            category_id="3063",
            enriched_at=datetime.now(UTC),
        )
    )
    remaining = store.pending_enrichment(RUN_ID)
    assert [pid for pid, _ in remaining] == ["222"]

    stats = store.enrichment_stats(RUN_ID)
    assert stats["ok"] == 1
    assert stats["pending"] == 1


def test_store_export_reference_schema(store: CatalogStore, tmp_path: Path):
    store.save_product(make_product("111"))
    store.record_hit(
        crawl_run_id=RUN_ID, product_id="111", keyword="iphone", page=1, rank_in_page=3
    )
    store.record_hit(
        crawl_run_id=RUN_ID, product_id="111", keyword="case hp", page=1, rank_in_page=7
    )
    store.save_enrichment(
        EnrichmentResult(
            crawl_run_id=RUN_ID,
            product_id="111",
            status="ok",
            review_count=42,
            sold=1200,
            rating=4.8,
            category_id="3063",
            enriched_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    out = tmp_path / "export" / "tokopedia_products_v2.csv"
    store.export_products_csv(out, RUN_ID)

    import pandas as pd

    df = pd.read_csv(out)
    assert tuple(df.columns) == EXPORT_COLUMNS
    row = df.iloc[0]

    # Enrichment values override search-layer values
    assert row["review_count"] == 42
    assert row["sold"] == 1200
    assert row["rating"] == 4.8
    # Derived fields
    assert row["category"] == "handphone-tablet"
    assert row["n_keyword_hits"] == 2
    assert row["sort"] == "relevance"
    assert row["page_number"] == 1
    assert row["rank_in_page"] == 3
    assert row["crawler_version"] == CRAWLER_VERSION
    # WIB timestamp (+07:00)
    assert "+07:00" in row["crawl_timestamp"]


def test_store_export_without_enrichment_falls_back(store: CatalogStore, tmp_path: Path):
    """sold falls back to sold_count_floor, rating stays from search."""
    store.save_product(make_product("333", rating=4.5, sold_count_floor=100))
    store.record_hit(
        crawl_run_id=RUN_ID, product_id="333", keyword="iphone", page=1, rank_in_page=1
    )

    out = tmp_path / "export2.csv"
    store.export_products_csv(out, RUN_ID)

    import pandas as pd

    df = pd.read_csv(out)
    row = df.iloc[0]
    assert row["review_count"] is None or pd.isna(row["review_count"])
    assert row["sold"] == 100
    assert row["rating"] == 4.5


# --------------------------------------------------------------------- enrich

APOLLO_HTML = """
<html><head><script>
window.__APOLLO_STATE__ = {"ROOT_QUERY": {"pdp": {"basicInfo": {
  "stats": {"countReview": 42, "rating": 4.8},
  "txStats": {"countSold": 1200},
  "category": {"id": 3063, "name": "Aksesoris Handphone"}
}}}};
</script></head><body>ok</body></html>
"""

JSONLD_ONLY_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "Product", "name": "Case HP", "aggregateRating": {"ratingValue": 4.6, "reviewCount": 17}}
</script>
</head><body><span>217 terjual</span></body></html>
"""

DOM_ONLY_HTML = '<html><body><span>100+ terjual</span></body></html>'


def test_extract_metrics_from_apollo():
    m = extract_pdp_metrics_from_html(APOLLO_HTML)
    assert m.review_count == 42
    assert m.sold == 1200
    assert m.rating == 4.8
    assert m.category_id == "3063"
    assert m.sources == {"apollo"}
    assert m.any_found


def test_extract_metrics_jsonld_and_dom_fallback():
    m = extract_pdp_metrics_from_html(JSONLD_ONLY_HTML)
    assert m.review_count == 17
    assert m.rating == 4.6
    assert m.sold == 217  # DOM fallback
    assert "jsonld" in m.sources
    assert "dom" in m.sources


def test_extract_metrics_dom_only():
    m = extract_pdp_metrics_from_html(DOM_ONLY_HTML)
    assert m.sold == 100
    assert m.review_count is None


def test_extract_metrics_nothing_found():
    m = extract_pdp_metrics_from_html("<html><body>captcha</body></html>")
    assert not m.any_found


def test_extract_metrics_malformed_apollo():
    m = extract_pdp_metrics_from_html(
        '<html><script>window.__APOLLO_STATE__ = {"broken": ;};</script></html>'
    )
    assert not m.any_found


def test_apollo_extraction_via_json_roundtrip():
    """Simulate a real Apollo payload shape (nested under PDP response key)."""
    payload = {
        "PDPResponse:1": {
            "basicInfo": {
                "stats": {"countReview": 3, "rating": 5.0},
                "txStats": {"countSold": 11},
            }
        }
    }
    html = f"<html><script>window.__APOLLO_STATE__ = {json.dumps(payload)};</script></html>"
    m = extract_pdp_metrics_from_html(html)
    assert m.review_count == 3
    assert m.sold == 11
    assert m.rating == 5.0


NORMALIZED_CACHE_HTML = (
    "<html><head><script>window.__PAGE_TYPE__ = 'pdp';</script>"
    "<script>window.__cache = {"
    '"ROOT_QUERY": {}, '
    '"pdpBasicInfo102447352126": {'
    '"productID": "102447352126", '
    '"stats": {"type": "id", "id": "$pdpBasicInfo102447352126.stats"}, '
    '"txStats": {"type": "id", "id": "$pdpBasicInfo102447352126.txStats"}, '
    '"category": {"type": "id", "id": "pdpCategory3063"}'
    "}, "
    '"$pdpBasicInfo102447352126.stats": {"countReview": "42", "rating": 5}, '
    '"$pdpBasicInfo102447352126.txStats": {"countSold": "1200"}, '
    '"pdpCategory3063": {"id": "3063", "name": "Hard Case Handphone"}'
    "};</script></head><body>x</body></html>"
)


def test_extract_metrics_from_normalized_cache():
    """Current PDP format: window.__cache with pdpBasicInfo entity + refs."""
    m = extract_pdp_metrics_from_html(NORMALIZED_CACHE_HTML)
    assert m.review_count == 42
    assert m.sold == 1200
    assert m.rating == 5.0
    assert m.category_id == "3063"
    assert m.sources == {"apollo"}


def test_extract_metrics_prefers_cache_over_legacy_state():
    """Cache tier wins when both formats present (legacy only used when empty)."""
    both = NORMALIZED_CACHE_HTML.replace(
        "</body>",
        "<script>window.__APOLLO_STATE__ = {\"x\": {\"basicInfo\": "
        "{\"stats\": {\"countReview\": 7}}}};</script></body>",
    )
    m = extract_pdp_metrics_from_html(both)
    assert m.review_count == 42


def test_store_export_require_enrichment(store: CatalogStore, tmp_path: Path):
    """require_enrichment=True exports only enriched rows."""
    store.save_product(make_product("111"))
    store.save_product(make_product("222"))
    for pid in ("111", "222"):
        store.record_hit(crawl_run_id=RUN_ID, product_id=pid, keyword="iphone", page=1, rank_in_page=1)
    store.save_enrichment(
        EnrichmentResult(
            crawl_run_id=RUN_ID,
            product_id="111",
            status="ok",
            review_count=5,
            enriched_at=datetime.now(UTC),
        )
    )

    import pandas as pd

    out_all = tmp_path / "all.csv"
    store.export_products_csv(out_all, RUN_ID)
    out_enriched = tmp_path / "enriched.csv"
    store.export_products_csv(out_enriched, RUN_ID, require_enrichment=True)

    assert len(pd.read_csv(out_all)) == 2
    df_enriched = pd.read_csv(out_enriched)
    assert len(df_enriched) == 1
    assert str(df_enriched.iloc[0]["product_id"]) == "111"
