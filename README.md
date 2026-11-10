# Tokopedia Laptop Dataset Scraper

A restartable, polite, research-grade Scrapling crawler and ML dataset pipeline that collects, cleans, audits, and validates public Tokopedia laptop product listings into reproducible raw JSONL, processed CSV/Parquet datasets, and Kaggle release packages.

---

## 🛠️ Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
```

---

## 🚀 Usage & Basic Commands

Start a crawl:
```bash
laptop-scraper crawl --seed-config config/seeds.yaml --crawl-dir crawl_state/tokopedia_laptop --max-items 5000
```

Export dataset to CSV and Parquet:
```bash
laptop-scraper export --run-id <run-id>
```

Generate quality report:
```bash
laptop-scraper quality --run-id <run-id>
```

Inspect crawl stats:
```bash
laptop-scraper inspect --run-id <run-id>
```

---

## 🛒 Multi-Category Catalog Pipeline (v2)

Replicates the `yusepahmad/data-tokped-pml` reference dataset: fast search-only
collection across 45+ keywords in all categories, balanced between Official
Store (`shop_tier=2`) and Gold Merchant (`shop_tier=1`) via the `shop_tier`
search filter, then PDP enrichment for `review_count` and exact `sold`
(checkpoint/resume). Produces a 27-column CSV matching the reference schema
(`tokopedia_products_v2.csv`).

```bash
# 1. Collect — 45 keywords × 2 tiers × 2 pages ≈ 8–10k unique products (~10 min)
laptop-scraper catalog-collect --seed-config config/catalog_seeds.yaml --crawl-dir crawl_state/catalog

# 2. Enrich — review_count + sold exact from product pages (rerun to resume; --limit to batch)
laptop-scraper catalog-enrich --run-id <run-id> --crawl-dir crawl_state/catalog --limit 500

# 3. Export — merged CSV in reference schema.
#    --require-enrichment menyaring hanya baris yang sudah ter-enrich PDP
#    (semantik identik dataset referensi: review_count & sold selalu dari halaman produk)
laptop-scraper catalog-export --run-id <run-id> --crawl-dir crawl_state/catalog --require-enrichment

# 4. Cluster
python scripts/k_mean.py

# 5. Verifikasi kompatibilitas data untuk notebook DBSCAN Colab
#    (port headless Bagian 3/5/6/7/8 notebook: skenario P0-P4, eps via kneed, ARI stabilitas)
python scripts/dbscan_check.py
```

Smoke-test a subset first: `catalog-collect --keywords "iphone" --max-pages 1`.
Scale further by adding keywords to `config/catalog_seeds.yaml` or raising
`max_pages_per_task`; the params builder also supports `pmin`/`pmax` price-band
slicing for deeper catalog coverage.

---

## 🔄 End-to-End Pipeline Workflow (Crawl to Kaggle Push)

### 1. Ingestion & Crawling (Data Acquisition)

Collect Tokopedia search listings into SQLite state database and raw JSONL records:

```bash
# Start search crawl
laptop-scraper crawl --seed-config config/seeds.yaml --crawl-dir crawl_state/smoke-250 --max-pages 50

# Audit ML dataset readiness
laptop-scraper audit-ml-readiness --run-id 20260823T043405Z-2m8c6r37 --crawl-dir crawl_state/smoke-250
```

---

### 2. Dataset Cleaning, Reconciliation & Freeze

Classify semantic eligibility, exclude down payments and standalone component/accessory listings (RAM, LCD screens, chargers), resolve missing review count semantics (`KEEP_MISSING`), and generate frozen matrices R1 (`price + rating`) and R2 (`price + rating + review_count`):

```bash
laptop-scraper freeze-ml-dataset \
  --run-id 20260823T043405Z-2m8c6r37 \
  --config config/ml_freeze.yaml \
  --output-dir data/ml/smoke-250 \
  --review-decisions reviews/ml_freeze/20260823T043405Z-2m8c6r37/low_price_review_decisions.csv \
  --baseline-decisions data/ml/smoke-250/ml-dataset-v1.0.2/cleaning_decisions.csv \
  --baseline-artifact ml-dataset-v1.0.2 \
  --artifact-version ml-dataset-v1.0.3 \
  --strict
```

---

### 3. Verification & Code Quality

Run automated test suite and linter checks:

```bash
pytest -v
ruff check src tests scripts
```

---

### 4. Kaggle Packaging & Dataset Card Generation

Bundle Parquet and CSV files, audit ledgers, metadata, and Kaggle Dataset Card into `kaggle/release/v1.0.3/`:

```bash
python scripts/prepare_kaggle_release.py \
  --source-dir data/ml/smoke-250/ml-dataset-v1.0.3 \
  --output-dir kaggle/release/v1.0.3 \
  --dataset-id YOUR_KAGGLE_USERNAME/tokopedia-laptop-market-dataset
```

---

### 5. Publishing to Kaggle

Publish dataset release using Kaggle CLI helper:

```bash
# Create new dataset
python scripts/publish_kaggle.py \
  --release-dir kaggle/release/v1.0.3 \
  --new \
  --owner YOUR_KAGGLE_USERNAME

# Update existing dataset version
python scripts/publish_kaggle.py \
  --release-dir kaggle/release/v1.0.3 \
  --notes "Release v1.0.3 - Tokopedia Laptop ML Dataset" \
  --owner YOUR_KAGGLE_USERNAME
```

---

## 📊 Dataset Accounting Summary (`ml-dataset-v1.0.3`)

| Category / Metric | Value |
| :--- | :--- |
| **Total Source Ingested Listings** | `2,227` (100% accounted) |
| **Semantically Valid Laptop Products** | `2,163` (97.13%) |
| **Excluded Non-Laptop Observations** | `64` (2.87%) |
| **Primary Representation R1 (`price + rating`)** | `2,106` complete cases |
| **Secondary Representation R2 (`price + rating + review_count`)** | `1,588` complete cases |
| **Low-Price Queue Audited** | `20 / 20` (100% `APPROVED_VALID`) |
| **Final Release Status** | `ML_DATASET_V1_FINAL` |

---

## 📚 Documentation References

- [Full End-to-End Pipeline Guide](docs/pipeline-workflow-guide.md)
- [Final Dataset Release Spec (`v1.0.3`)](docs/ml-dataset-final-release.md)
- [Kaggle Release Design Spec](docs/superpowers/specs/2026-08-23-kaggle-dataset-release-design.md)
