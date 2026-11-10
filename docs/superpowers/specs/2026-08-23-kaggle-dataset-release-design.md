# Kaggle Dataset Release Setup Design Spec

> **Date:** 2026-08-23  
> **Source Dataset Artifact:** `ml-dataset-v1.0.3`  
> **Target Release Location:** `kaggle/release/v1.0.3/`  
> **Target Dataset Slug:** `muhfalihr/tokopedia-laptop-market-dataset`  
> **License:** `CC-BY-SA-4.0`  
> **Status:** Approved Design Spec  

---

## 1. Executive Summary

This design spec defines the downstream publication packaging for releasing the frozen Tokopedia laptop dataset (`ml-dataset-v1.0.3`) to Kaggle Datasets.

The dataset release setup creates a dedicated, immutable Kaggle release directory `kaggle/release/v1.0.3/` containing metadata, formatted CSV and Parquet representations, audit ledgers, a rich Kaggle Dataset Card, and automated helper scripts for preparation and publishing.

---

## 2. Global Constraints & Integrity Invariants

1. **Source Invariance:** Never mutate the source acquisition data (`2,227` listings) or the frozen dataset matrices/manifest (`R1: 2,106`, `R2: 1,588`, `Excluded: 64`).
2. **Credential Safety:** Do not store Kaggle API keys, tokens, or credentials in repository files or git history.
3. **Dual Representation Format:** Provide both `.parquet` and `.csv` files for R1 and R2 to support both programmatic consumption (Parquet) and Kaggle web UI browser data preview (CSV).
4. **Metadata Provenance:** All numbers, column descriptions, and semantic rules in the Kaggle Dataset Card must be directly populated from `ml_dataset_manifest.json` and `RELEASE_SIGNOFF.md`.

---

## 3. Packaging & Directory Layout

```text
kaggle/
└── release/v1.0.3/
    ├── r1_price_rating.parquet
    ├── r1_price_rating.csv
    ├── r2_price_rating_review_count.parquet
    ├── r2_price_rating_review_count.csv
    ├── cleaning_decisions.csv
    ├── excluded_observations.csv
    ├── low_price_review_decisions.csv
    ├── ml_dataset_manifest.json
    ├── dataset-metadata.json
    └── README.md                       # Kaggle Dataset Card
scripts/
├── prepare_kaggle_release.py           # Ingests ml-dataset-v1.0.3 & generates release package
└── publish_kaggle.py                   # Helper script for Kaggle CLI publishing
```

---

## 4. Kaggle Dataset Metadata (`dataset-metadata.json`)

```json
{
  "title": "Tokopedia Laptop Market Dataset (2026)",
  "id": "muhfalihr/tokopedia-laptop-market-dataset",
  "licenses": [
    {
      "name": "CC-BY-SA-4.0"
    }
  ],
  "subtitle": "Cleaned, audited, and semantically reconciled dataset of Tokopedia laptop search listings",
  "keywords": [
    "indonesia",
    "e-commerce",
    "laptops",
    "market-research",
    "data-cleaning",
    "clustering"
  ]
}
```

---

## 5. Dataset Card Structure (`README.md`)

The Kaggle Dataset Card will contain:

1. **Header & Badges:** Title, version `v1.0.3`, license `CC-BY-SA-4.0`, source run ID `20260823T043405Z-2m8c6r37`.
2. **Context & Overview:** Research intent, e-commerce domain background, and acquisition summary (`2,227` listings).
3. **Data Files & Column Specifications:**
   - `r1_price_rating.csv` / `.parquet`: `listing_key`, `product_name`, `product_url`, `price`, `rating` (`2,106` rows).
   - `r2_price_rating_review_count.csv` / `.parquet`: `listing_key`, `product_name`, `product_url`, `price`, `rating`, `review_count` (`1,588` rows).
   - `cleaning_decisions.csv`: Complete 12-column decision ledger (`2,227` rows).
   - `excluded_observations.csv`: Excluded non-laptop listings (`64` rows).
   - `low_price_review_decisions.csv`: Audited low-price review queue (`20` rows).
4. **Data Cleaning & Semantic Rules:**
   - Down payment and deposit list price exclusions.
   - Primary product head identity classification (excludes RAM, LCD screens, power chargers, locks, paper notebooks).
   - Missing review count policy (`KEEP_MISSING`; no null-to-zero recoding).
5. **Cryptographic Signoff & Reproducibility:** SHA-256 hashes, Git commit tags, and dataset manifest linkage.
6. **Limitations & Disclaimer:** Search snapshot nature and seller self-reporting context.

---

## 6. Helper Scripts Architecture

### `scripts/prepare_kaggle_release.py`
- Ingests `data/ml/smoke-250/ml-dataset-v1.0.3/` (or specified artifact path).
- Creates `kaggle/release/v1.0.3/`.
- Reads `r1_price_rating.parquet` and `r2_price_rating_review_count.parquet` and writes `r1_price_rating.csv` and `r2_price_rating_review_count.csv`.
- Copies `cleaning_decisions.csv`, `excluded_observations.csv`, `low_price_review_decisions.csv`, `ml_dataset_manifest.json`.
- Renders `dataset-metadata.json` and `README.md`.
- Validates row counts and SHA-256 hashes.

### `scripts/publish_kaggle.py`
- Checks whether `kaggle` CLI tool is installed.
- Checks whether Kaggle credentials (`kaggle.json`) are present.
- Executes `kaggle datasets create -p kaggle/release/v1.0.3` or `kaggle datasets version -p kaggle/release/v1.0.3 -m "Release v1.0.3"`.
- Output instructions for web UI upload fallback if CLI credentials are not configured.

---

## 7. Spec Self-Review

1. **Placeholder Scan:** Zero `TBD`, `TODO`, or unassigned variables.
2. **Internal Consistency:** File paths, row counts, and metadata schema match `ml-dataset-v1.0.3` manifest exactly.
3. **Scope Check:** Strictly focused on Kaggle release artifact packaging and scripts; zero modeling code added.
4. **Ambiguity Check:** Explicit file list, column schemas, and CLI commands defined.
