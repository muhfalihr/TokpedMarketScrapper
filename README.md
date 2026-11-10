# TokpedMarketScrapper

Scraper dan pipeline dataset produk Tokopedia berbasis Scrapling: koleksi multi-kategori via API pencarian GraphQL, enrichment halaman produk, dan ekspor dataset 27 kolom siap clustering — kompatibel langsung dengan notebook DBSCAN/K-Means Colab.

## Instalasi

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Quickstart — Pipeline Katalog (utama)

```bash
tokped-scraper catalog-collect --crawl-dir crawl_state/catalog            # 1. kumpulkan (±10 menit)
tokped-scraper catalog-enrich --run-id <run-id> --limit 500              # 2. enrich (ulangi sampai habis)
tokped-scraper catalog-export --run-id <run-id> --require-enrichment     # 3. ekspor CSV skema referensi
python scripts/k_mean.py                                                  # 4. clustering
```

Mulai dari smoke test kecil: `catalog-collect --keywords "iphone" --max-pages 1`.

## Pipeline Laptop (legacy)

Pipeline laptop satu kategori (crawl → freeze → audit → Kaggle) tetap tersedia via `crawl` / `freeze-ml-dataset` / `audit-ml-readiness` — lihat [docs/pipeline-workflow-guide.md](docs/pipeline-workflow-guide.md).

## Dokumentasi

| Dokumen | Isi |
|---|---|
| [docs/catalog-pipeline.md](docs/catalog-pipeline.md) | Panduan lengkap pipeline katalog: arsitektur, parameter, skema 27 kolom, ekspansi volume data |
| [docs/pipeline-workflow-guide.md](docs/pipeline-workflow-guide.md) | Alur kerja pipeline laptop end-to-end sampai Kaggle |
| [docs/ml-dataset-final-release.md](docs/ml-dataset-final-release.md) | Spesifikasi rilis dataset laptop v1.0.3 |

## Pengembangan

```bash
pytest -q                                   # 507 test
ruff check src tests scripts                # lint
```

---

*Data bersumber dari halaman publik Tokopedia untuk keperluan akademik nonkomersial; pengambilan otomatis dapat bertentangan dengan ketentuan layanan Tokopedia.*
