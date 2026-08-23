# End-to-End Pipeline Guide: From Crawl to Kaggle Push

Panduan alur kerja lengkap (End-to-End Workflow) repositori **Tokped-Scrapper** mulai dari pengambilan data (*crawling/scraping*), pembersihan dataset (*ML Freeze & Audit*), hingga publikasi rilis ke **Kaggle Datasets**.

---

## 📋 Prerequisites & Setup

Sebelum menjalankan pipeline, pastikan virtual environment Python sudah aktif:

```powershell
# Buat dan aktifkan virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package beserta dependensinya
.venv\Scripts\pip.exe install -e .
```

---

## 🗂️ Overview Alur Kerja Pipeline (5 Fase)

```text
[Fase 1: Ingestion & Crawl] ➡️ [Fase 2: Dataset Cleaning & Freeze] ➡️ [Fase 3: Validation & Signoff] ➡️ [Fase 4: Kaggle Packaging] ➡️ [Fase 5: Kaggle Publish]
```

---

## 🚀 Langkah 1: Ingestion & Crawling (Data Acquisition)

Jalankan crawler untuk mengumpulkan listing pencarian produk laptop dari Tokopedia ke SQLite DB & file raw JSONL.

```powershell
# 1. Jalankan crawl pencarian laptop
.venv\Scripts\python.exe -m laptop_market_scraper.cli crawl-search `
  --query "laptop" `
  --max-pages 50 `
  --run-id 20260823T043405Z-2m8c6r37

# 2. Evaluasi kesiapan data hasil crawl (Acquisition Readiness)
.venv\Scripts\python.exe -m laptop_market_scraper.cli evaluate-acquisition `
  --db-path crawl_state/smoke-250/laptops.db `
  --output-dir reports/smoke-250
```

---

## 🧹 Langkah 2: Dataset Cleaning, Reconciliation & Freeze

Proses ini melakukan klasifikasi semantic eligibility, pembersihan harga down payment, resolusi missing value `review_count`, pembuatan matriks `R1` & `R2`, dan evaluasi manual review queue.

```powershell
# 1. Jalankan pembekuan dataset (ML Dataset Freeze) dengan strict mode
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

*Hasil output akan tersimpan di: `data/ml/smoke-250/ml-dataset-v1.0.3/`*

---

## 🧪 Langkah 3: Pengujian & Verifikasi Integritas Codebase

Verifikasi seluruh unit test dan kualitas kode sebelum melakukan publikasi.

```powershell
# 1. Jalankan seluruh unit test suite
.venv\Scripts\python.exe -m pytest -v

# 2. Jalankan linter check
.venv\Scripts\ruff.exe check src tests scripts
```

---

## 📦 Langkah 4: Packaging Bundle Dataset Kaggle

Generate folder publikasi Kaggle (`kaggle/release/v1.0.3/`) yang berisi file `.parquet`, `.csv` (R1 & R2), log audit, `dataset-metadata.json`, dan Kaggle Dataset Card (`README.md`).

```powershell
# Generate bundle Kaggle dari dataset v1.0.3
.venv\Scripts\python.exe scripts/prepare_kaggle_release.py `
  --source-dir data/ml/smoke-250/ml-dataset-v1.0.3 `
  --output-dir kaggle/release/v1.0.3 `
  --dataset-id YOUR_KAGGLE_USERNAME/tokopedia-laptop-market-dataset
```

---

## 📤 Langkah 5: Publikasi Dataset ke Kaggle

Upload paket dataset yang telah di-package ke Kaggle menggunakan CLI helper.

```powershell
# 1. Opsi A: Jika membuat Dataset BARU (First Time Upload)
.venv\Scripts\python.exe scripts/publish_kaggle.py `
  --release-dir kaggle/release/v1.0.3 `
  --new `
  --owner YOUR_KAGGLE_USERNAME

# 2. Opsi B: Jika memperbarui Versi Dataset yang SUDAH ADA
.venv\Scripts\python.exe scripts/publish_kaggle.py `
  --release-dir kaggle/release/v1.0.3 `
  --notes "Release v1.0.3 - Tokopedia Laptop ML Dataset" `
  --owner YOUR_KAGGLE_USERNAME
```

*(Catatan: Ganti `YOUR_KAGGLE_USERNAME` dengan username Kaggle Anda).*

---

## 🛠️ Alternatif Upload Manual (Web UI Kaggle)

Jika tidak menggunakan Kaggle CLI:
1. Buka [https://www.kaggle.com/datasets](https://www.kaggle.com/datasets) lalu klik **+ New Dataset**.
2. Upload seluruh file dari folder [`kaggle/release/v1.0.3/`](file:///D:/CLASS%20UPH/MACHINE-LEARNING/REPOS/Tokped-Scrapper/kaggle/release/v1.0.3/).
3. Copy isi file [`kaggle/release/v1.0.3/README.md`](file:///D:/CLASS%20UPH/MACHINE-LEARNING/REPOS/Tokped-Scrapper/kaggle/release/v1.0.3/README.md) ke kolom deskripsi **About Dataset**.
