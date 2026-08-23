# Tokopedia Laptop Market Dataset (2026)

> **Dataset Version:** `ml-dataset-v1.0.3`  
> **License:** Creative Commons Attribution-ShareAlike 4.0 International (`CC-BY-SA-4.0`)  
> **Source Run ID:** `20260823T043405Z-2m8c6r37`  
> **Source Accounting:** `2227` total search listings ingested  
> **Release Status:** `KAGGLE_RELEASE_READY`  

---

## 1. Context & Research Scope

This dataset contains a cleaned, audited, and semantically reconciled product-listing snapshot of Tokopedia laptop search results obtained during the 2026 crawl period.

The dataset is specifically structured for machine learning research, including:
- **Unsupervised Clustering:** Identifying laptop market segments (budget, mid-range, gaming, flagship).
- **Price Sensitivity & Segmentation:** Analyzing pricing behavior and rating distributions across brands.
- **Data Cleaning Methodology:** Auditing e-commerce noise, component/accessory leakage, and missing data patterns.

---

## 2. Dataset Accounting & File Inventory

| File Name | Format | Rows | Description |
| :--- | :--- | :--- | :--- |
| `r1_price_rating.csv` / `.parquet` | Tabular | `2106` | Primary representation R1 (`price`, `rating`) complete cases |
| `r2_price_rating_review_count.csv` / `.parquet` | Tabular | `1588` | Secondary representation R2 (`price`, `rating`, `review_count`) complete cases |
| `cleaning_decisions.csv` | CSV | `2227` | Complete 12-column audit decision ledger for every listing |
| `excluded_observations.csv` | CSV | `64` | Explicit non-laptop component/accessory exclusion evidence |
| `low_price_review_decisions.csv` | CSV | `20` | Audited low-price (< Rp2,000,000) manual review queue |
| `ml_dataset_manifest.json` | JSON | N/A | Cryptographic manifest with SHA-256 hashes and git commit lineage |

---

## 3. Data Dictionary & Column Specifications

### Representation R1 (`r1_price_rating.csv` / `.parquet`)
- `listing_key` *(string)*: Unique primary key for the product listing.
- `product_name` *(string)*: Full cleaned product title on Tokopedia.
- `product_url` *(string)*: Canonical product URL.
- `price` *(integer)*: List price in Indonesian Rupiah (IDR).
- `rating` *(float)*: User rating score between 0.0 and 5.0.

### Representation R2 (`r2_price_rating_review_count.csv` / `.parquet`)
- `listing_key` *(string)*: Unique primary key for the product listing.
- `product_name` *(string)*: Full cleaned product title.
- `product_url` *(string)*: Canonical product URL.
- `price` *(integer)*: List price in IDR.
- `rating` *(float)*: User rating score (0.0 to 5.0).
- `review_count` *(integer)*: Total verified buyer reviews (strictly >= 0).

### Decision Ledger (`cleaning_decisions.csv`)
Contains 12 columns: `listing_key`, `product_name`, `product_url`, `price`, `rating`, `review_count_original`, `review_count_resolved`, `eligibility_decision`, `eligibility_reason`, `review_count_status`, `include_r1`, `include_r2`, `exclusion_reasons_r1`, `exclusion_reasons_r2`, `evidence`.

---

## 4. Semantic Cleaning Rules

Listings were cleaned using a 4-tier semantic precedence system:
1. **Invalid Price Filter:** Excludes listings where list price is a down payment, deposit, or installment (`DP`, `Down Payment`, `Uang Muka`).
2. **Product Head Classifier:** Distinguishes physical laptops from standalone components (RAM sticks, LCD panels, replacement batteries, flex cables, casings) and accessories (chargers, locks, screen protectors, bubble wrap gift placeholders).
3. **Valid Laptop Preservation:** Laptops mentioning included accessories or specs (e.g., `Laptop Lenovo IdeaPad ... 16GB RAM SSD 512GB + Sleeve Bonus`) are strictly preserved as valid.
4. **Missing Review Count Policy (`KEEP_MISSING`):** Missing review counts are preserved as unresolved nulls and excluded from R2 complete cases; no missing review count is silently recoded to zero.

---

## 5. Provenance & Cryptographic Verification

- **Source Run ID:** `20260823T043405Z-2m8c6r37`
- **Source Acquisition Tag:** `dataset-acquisition-v1.0`
- **R1 Parquet SHA-256:** `00623b78e3ece31c12bb07e4848e85217737effb233a7d2fc1167b7c0eccbe49`
- **R2 Parquet SHA-256:** `026a6cf8dbda5dee099fa4716d8dbd4c7cf4a490654c68ee6fe380bc913bc9b9`

---

## 6. Limitations

- The dataset is a search-result snapshot from a frozen Tokopedia crawl configuration.
- Prices, ratings, and review counts reflect self-reported seller metadata on Tokopedia at scrape time.
