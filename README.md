# Tokopedia Laptop Dataset Scraper

A restartable, polite, research-grade Scrapling crawler and ML dataset pipeline that collects, cleans, audits, and validates public Tokopedia laptop product listings into reproducible raw JSONL, CSV/Parquet datasets, and Kaggle release packages.

---

## 🛠️ Installation

```powershell
# Create and activate virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package and dependencies
.venv\Scripts\pip.exe install -e .
```

---

## 🔄 End-to-End Pipeline Workflow (Crawl to Kaggle Push)

### 1. Ingestion & Crawling (Data Acquisition)

Collect Tokopedia search listings into SQLite state database and raw JSONL records:

```powershell
# Start search crawl
.venv\Scripts\python.exe -m laptop_market_scraper.cli crawl-search `
  --query "laptop" `
  --max-pages 50 `
  --run-id 20260823T043405Z-2m8c6r37

# Evaluate acquisition readiness
.venv\Scripts\python.exe -m laptop_market_scraper.cli evaluate-acquisition `
  --db-path crawl_state/smoke-250/laptops.db `
  --output-dir reports/smoke-250
```

---

### 2. Dataset Cleaning, Reconciliation & Freeze

Classify semantic eligibility, exclude down payments and standalone component/accessory listings (RAM, LCD screens, chargers), resolve missing review count semantics (`KEEP_MISSING`), and generate frozen matrices R1 (`price + rating`) and R2 (`price + rating + review_count`):

```powershell
.venv\Scripts\python.exe -m laptop_market_scraper.cli freeze-ml-dataset `
  --run-id 20260823T043405Z-2m8c6r37 `
  --config-path config/ml_freeze.yaml `
  --db-path crawl_state/smoke-250/laptops.db `
  --raw-jsonl-path crawl_state/smoke-250/raw/20260823T043405Z-2m8c6r37/products.jsonl `
  --readiness-json-path reports/smoke-250/ml_readiness.json `
  --extreme-review-path reports/smoke-250/extreme_price_review.csv `
  --missingness-review-path reports/smoke-250/missingness_cases.csv `
  --review-decisions-path reviews/ml_freeze/20260823T043405Z-2m8c6r37/low_price_review_decisions.csv `
  --baseline-decisions-path data/ml/smoke-250/ml-dataset-v1.0.2/cleaning_decisions.csv `
  --baseline-artifact ml-dataset-v1.0.2 `
  --artifact-version ml-dataset-v1.0.3 `
  --output-dir data/ml/smoke-250 `
  --strict
```

---

### 3. Verification & Code Quality

Run automated test suite and linter checks:

```powershell
.venv\Scripts\python.exe -m pytest -v
.venv\Scripts\ruff.exe check src tests scripts
```

---

### 4. Kaggle Packaging & Dataset Card Generation

Bundle Parquet and CSV files, audit ledgers, metadata, and Kaggle Dataset Card into `kaggle/release/v1.0.3/`:

```powershell
.venv\Scripts\python.exe scripts/prepare_kaggle_release.py `
  --source-dir data/ml/smoke-250/ml-dataset-v1.0.3 `
  --output-dir kaggle/release/v1.0.3 `
  --dataset-id YOUR_KAGGLE_USERNAME/tokopedia-laptop-market-dataset
```

---

### 5. Publishing to Kaggle

Publish dataset release using Kaggle CLI helper:

```powershell
# Create new dataset
.venv\Scripts\python.exe scripts/publish_kaggle.py `
  --release-dir kaggle/release/v1.0.3 `
  --new `
  --owner YOUR_KAGGLE_USERNAME

# Update existing dataset version
.venv\Scripts\python.exe scripts/publish_kaggle.py `
  --release-dir kaggle/release/v1.0.3 `
  --notes "Release v1.0.3 - Tokopedia Laptop ML Dataset" `
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
