# End-to-End Pipeline Guide: From Crawl to Kaggle Push

Panduan alur kerja lengkap (End-to-End Workflow) repositori **Tokped-Scrapper** menggunakan CLI `laptop-scraper` mulai dari pengambilan data (*crawling/scraping*), pembersihan dataset (*ML Freeze & Audit*), hingga publikasi rilis ke **Kaggle Datasets**.

---

## 📋 Prerequisites & Setup

Sebelum menjalankan pipeline, pastikan virtual environment Python sudah aktif dan package `laptop-scraper` terinstall:

```bash
# Buat dan aktifkan virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install package beserta CLI laptop-scraper
pip install -e .
```

---

## 🗂️ Overview Alur Kerja Pipeline (5 Fase)

```text
[Fase 1: Ingestion & Crawl] ➡️ [Fase 2: Dataset Cleaning & Freeze] ➡️ [Fase 3: Validation & Signoff] ➡️ [Fase 4: Kaggle Packaging] ➡️ [Fase 5: Kaggle Publish]
```

---

## 🚀 Langkah 1: Ingestion & Crawling (Data Acquisition)

Mengambil data listing pencarian produk laptop dari Tokopedia ke SQLite DB & file raw JSONL.

```bash
# 1. Jalankan crawl pencarian laptop menggunakan CLI laptop-scraper
laptop-scraper crawl --seed-config config/seeds.yaml --crawl-dir crawl_state/smoke-250 --max-pages 50

# 2. Evaluasi kesiapan data hasil crawl (ML Readiness Audit)
laptop-scraper audit-ml-readiness --run-id 20260823T043405Z-2m8c6r37 --crawl-dir crawl_state/smoke-250
```

---

## 🧹 Langkah 2: Dataset Cleaning, Reconciliation & Freeze

Proses ini melakukan klasifikasi semantic eligibility, pembersihan harga down payment, resolusi missing value `review_count`, pembuatan matriks `R1` & `R2`, dan evaluasi manual review queue.

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

*Hasil output akan tersimpan di: `data/ml/smoke-250/ml-dataset-v1.0.3/`*

---

## 🧪 Langkah 3: Pengujian & Verifikasi Integritas Codebase

Verifikasi seluruh unit test dan kualitas kode sebelum melakukan publikasi.

```bash
# 1. Jalankan seluruh unit test suite
pytest -v

# 2. Jalankan linter check
ruff check src tests scripts
```

---

## 📦 Langkah 4: Packaging Bundle Dataset Kaggle

Generate folder publikasi Kaggle (`kaggle/release/v1.0.3/`) yang berisi file `.parquet`, `.csv` (R1 & R2), log audit, `dataset-metadata.json`, dan Kaggle Dataset Card (`README.md`).

```bash
python scripts/prepare_kaggle_release.py \
  --source-dir data/ml/smoke-250/ml-dataset-v1.0.3 \
  --output-dir kaggle/release/v1.0.3 \
  --dataset-id YOUR_KAGGLE_USERNAME/tokopedia-laptop-market-dataset
```

---

## 📤 Langkah 5: Publikasi Dataset ke Kaggle

Upload paket dataset yang telah di-package ke Kaggle menggunakan CLI helper.

```bash
# 1. Opsi A: Jika membuat Dataset BARU (First Time Upload)
python scripts/publish_kaggle.py \
  --release-dir kaggle/release/v1.0.3 \
  --new \
  --owner YOUR_KAGGLE_USERNAME

# 2. Opsi B: Jika memperbarui Versi Dataset yang SUDAH ADA
python scripts/publish_kaggle.py \
  --release-dir kaggle/release/v1.0.3 \
  --notes "Release v1.0.3 - Tokopedia Laptop ML Dataset" \
  --owner YOUR_KAGGLE_USERNAME
```

*(Catatan: Ganti `YOUR_KAGGLE_USERNAME` dengan username Kaggle Anda).*

---

## 🛠️ Alternatif Upload Manual (Web UI Kaggle)

Jika tidak menggunakan Kaggle CLI:
1. Buka [https://www.kaggle.com/datasets](https://www.kaggle.com/datasets) lalu klik **+ New Dataset**.
2. Upload seluruh file dari folder [`kaggle/release/v1.0.3/`](file:///D:/CLASS%20UPH/MACHINE-LEARNING/REPOS/Tokped-Scrapper/kaggle/release/v1.0.3/).
3. Copy isi file [`kaggle/release/v1.0.3/README.md`](file:///D:/CLASS%20UPH/MACHINE-LEARNING/REPOS/Tokped-Scrapper/kaggle/release/v1.0.3/README.md) ke kolom deskripsi **About Dataset**.
