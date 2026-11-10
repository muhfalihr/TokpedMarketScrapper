# Pipeline Katalog Multi-Kategori (v2) — Panduan Lengkap

Pipeline utama **TokpedMarketScrapper**: replikasi pendekatan dataset referensi
(`yusepahmad/data-tokped-pml` / `tokopedia_products_v2.csv`) — koleksi cepat
berbasis API pencarian, seimbang antara toko resmi dan Gold Merchant, lalu
enrichment halaman produk untuk `review_count` dan `sold` exact.

---

## Arsitektur

```text
config/catalog_seeds.yaml
  (45 keyword × shop_tier 2/1 × 2 halaman)
        │
        ▼
CatalogCollectSpider ── POST GraphQL searchProductV5 ──► simpan langsung
  (tanpa kunjungi halaman produk; 60 produk/request)      ke CatalogStore
                                                          (SQLite + JSONL)
        │
        ▼
CatalogEnrichSpider ── GET halaman produk ──► ekstrak window.__cache (Apollo):
  (checkpoint/resume, jalankan ulang utk lanjut)   stats.countReview, rating,
                                                   txStats.countSold, category.id
        │
        ▼
catalog-export ──► tokopedia_products_v2.csv (27 kolom, skema identik referensi)
```

**Mengapa data jadi tidak skewed:** tanpa filter, urutan relevansi Tokopedia
hampir hanya mengembalikan toko resmi (terverifikasi: sampel 1.080 produk 100%
toko resmi). Filter `shop_tier` memaksa keseimbangan — hasil verifikasi live:
mix 50/50 (60 toko resmi tier 2, 60 Gold Merchant tier 3).

---

## Alur Kerja Lengkap

```bash
# 0. (Opsional) Smoke test kecil dulu: 1 keyword × 2 tier × 1 halaman
laptop-scraper catalog-collect --keywords "iphone" --max-pages 1 --crawl-dir crawl_state/catalog-smoke

# 1. Collect — 45 keyword × 2 tier × 2 halaman ≈ 8–10 ribu produk unik (±10 menit)
laptop-scraper catalog-collect --crawl-dir crawl_state/catalog

# 2. Enrich — review_count + sold exact dari halaman produk.
#    Batch dengan --limit; jalankan berulang sampai pending habis (otomatis resume).
#    --retry-failed untuk mencoba ulang yang gagal.
laptop-scraper catalog-enrich --run-id <run-id> --crawl-dir crawl_state/catalog --limit 500

# 3. Export — CSV 27 kolom skema referensi.
#    --require-enrichment: hanya baris yang sudah ter-enrich PDP
#    (review_count & sold selalu angka exact — semantik identik dataset referensi;
#    wajib untuk notebook DBSCAN Colab agar tidak ada NaN).
laptop-scraper catalog-export --run-id <run-id> --crawl-dir crawl_state/catalog --require-enrichment

# 4. Clustering K-Means (fallback otomatis ke dataset lama bila export tidak ada)
python scripts/k_mean.py

# 5. Validasi data untuk notebook DBSCAN (port headless Bagian 3/5/6/7/8 notebook)
python scripts/dbscan_check.py
```

---

## Skema Output (27 kolom)

`product_id, name, price, rating, review_count, sold, sold_label, category,
category_breadcrumb, category_id, url, shop_name, shop_city, is_official,
source_keyword, sort, discount_pct, original_price_fmt, original_price,
crawl_timestamp, page_number, rank_in_page, shop_id, shop_tier, is_ad,
n_keyword_hits, crawler_version`

Sumber per kolom:

| Kolom | Sumber | Catatan |
|---|---|---|
| `sold`, `review_count`, `rating`, `category_id` | halaman produk (enrichment) | `rating` fallback ke search; `sold` fallback ke batas bawah label (mis. "100+ terjual" → 100) |
| `sold_label`, `discount_pct`, `original_price`, `shop_*`, `is_official`, `is_ad`, `category_breadcrumb` | API pencarian | `is_official` dari badge official store / shop tier; `is_ad` dari objek ads |
| `page_number`, `rank_in_page`, `source_keyword`, `n_keyword_hits` | provenance | posisi & jumlah keyword yang menemukan produk |
| `crawl_timestamp` | derived | ISO 8601 WIB (+07:00) |

---

## Ekspansi Volume Data

- **Tambah keyword** di `config/catalog_seeds.yaml` (bebas, satu baris satu keyword).
- **Naikkan `max_pages_per_task`** untuk halaman lebih dalam (guard fingerprint
  otomatis berhenti bila halaman berulang).
- **Price band**: builder parameter mendukung `pmin`/`pmax` untuk mengiris
  katalog per rentang harga — berguna saat pagination dalam sudah jenuh.
- **Tier ketiga**: `tiers` di config menerima nilai lain bila diperlukan.

## Catatan Teknis

- Endpoint: `POST https://gql.tokopedia.com/graphql/SearchProductV5Query`
  dengan kontrak GraphQL terbeku (`config/search_product_v5_contract.json`,
  SHA-256 diverifikasi).
- Politeness: konkurensi rendah + autothrottle (collect: 2 paralel, delay awal 2 s;
  enrich: 4 paralel, delay awal 1 s).
- Enrichment mengekstrak `window.__cache` (Apollo normalized cache) dengan
  resolusi referensi `pdpBasicInfo<id>` → `stats`/`txStats`/`category`;
  fallback JSON-LD dan DOM.
- Rasio keberhasilan enrichment terverifikasi live: 399/400 (99,75%).
