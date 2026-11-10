# Tokopedia Laptop ML Dataset Final Release (`ml-dataset-v1.0.3`)

> **Artifact Name:** `ml-dataset-v1.0.3` (Final Immutable Release)  
> **Source Run ID:** `20260823T043405Z-2m8c6r37` (smoke-250)  
> **Acquisition Tag:** `dataset-acquisition-v1.0`  
> **Git Commit:** `HEAD`  
> **Final Release Status:** `ML_DATASET_V1_FINAL`  

---

## 1. Research Scope & Dataset Boundaries

This dataset provides a cleaned, audited, and cryptographically verified product-listing snapshot of Tokopedia laptop search results for machine learning research (unsupervised clustering, price segmentation, and market structure analysis).

- **In-Scope:** Source data ingestion, semantic eligibility cleaning, review count resolution, dual feature representation materialization (R1 and R2), manual low-price review closure, and release verification.
- **Out-of-Scope (Repository Boundary):** Preprocessing (StandardScaler, MinMaxScaler, RobustScaler), dimensional reduction (PCA, t-SNE), clustering algorithms (K-Means, Agglomerative, GMM), model evaluation, and Kaggle API publication.

---

## 2. Acquisition Snapshot & Data Accounting

| Metric / Level | Value |
| :--- | :--- |
| **Total Source Ingested Listings** | `2,227` (Immutable) |
| **Semantically Valid Laptop Products** | `2,163` (97.13%) |
| **Excluded Observations** | `64` (2.87%) |
| **Ambiguous Observations** | `0` (0.00%) |
| **Primary Representation R1 (`price + rating`)** | `2,106` complete cases |
| **Secondary Representation R2 (`price + rating + review_count`)** | `1,588` complete cases |

---

## 3. Dataset Cleaning & Semantic Eligibility Rules

Listings are evaluated against a 4-tier precedence rule sequence to separate valid laptop products from components, accessories, stationery, and payment placeholders:

1. **Invalid Price Semantics:** Excludes listings where list price is a down payment, deposit, or installment payment (`DP`, `Down Payment`, `Uang Muka`, `Deposit`).
2. **Product-Head Identity Classification:** Primary product intent is classified as `LAPTOP`, `COMPONENT`, `ACCESSORY`, `PAPER_NOTEBOOK`, or `PLACEHOLDER`. Non-laptop primary product heads are excluded even if generic computer terms appear in the title.
3. **Component Matcher:** Excludes replacement screens/LCDs, SODIMM RAM sticks, replacement batteries, flex cables, SSDs, bracket frames, replacement keyboards, and replacement casings.
4. **Accessory Matcher:** Excludes gift bonus placeholders (bubble wrap, Office licenses), power adapters/chargers, security locks, screen/keyboard protectors, standalone sleeve cases, and sticker packs.

Valid laptops mentioning included accessories or specification details (e.g. `Laptop Lenovo IdeaPad ... RAM 16GB SSD 512GB + Sleeve Bonus`) are explicitly preserved as `VALID_LAPTOP`.

---

## 4. Review Count Missing-Value Policy

| Semantic Status | Count | Treatment in R1 / R2 |
| :--- | :--- | :--- |
| **Observed Count** (`> 0`) | 1,266 | Preserved verbatim in R1 and R2 |
| **Explicit Zero** (`= 0`) | 372 | Preserved verbatim as `0` in R1 and R2 |
| **Semantic Zero Proven** | 0 | None proven |
| **Missing / Unresolved Null** | 589 | Preserved as null (`KEEP_MISSING`). Included in R1 (`price + rating`), excluded from R2 (`price + rating + review_count`). |

*No unresolved missing `review_count` value is semantically recoded to zero.*

---

## 5. Manual Low-Price Review Closure Evidence

All 20 listings in the diagnostic low-price queue (`price < Rp2,000,000`) were manually audited using product semantics:
- **Required Reviews:** 20 listings
- **Resolved Reviews:** 20 listings (100% complete)
- **Approved Valid:** 20 listings (`APPROVED_VALID`)
- **Leakage Excluded:** 0 listings
- **Ambiguous Excluded:** 0 listings

All 20 low-price items represent physically complete second-hand, used, or refurbished laptops (Sony Vaio, Dell Latitude, Lenovo ThinkPad, HP EliteBook, Toshiba Dynabook) priced between Rp580,000 and Rp1,999,000. Price thresholding is diagnostic-only and never automatically excludes a product.

---

## 6. Immutable Artifact Inventory & Hashes

| Artifact File | Description | SHA-256 Hash |
| :--- | :--- | :--- |
| `r1_price_rating.parquet` | R1 complete case matrix (`2,106` rows) | `00623b78e3ece31c12bb07e4848e85217737effb233a7d2fc1167b7c0eccbe49` |
| `r2_price_rating_review_count.parquet` | R2 complete case matrix (`1,588` rows) | `026a6cf8dbda5dee099fa4716d8dbd4c7cf4a490654c68ee6fe380bc913bc9b9` |
| `cleaning_decisions.csv` | Full audit decision ledger (`2,227` rows) | `5da5da47a050ef369ac8f15abcb2e2e1593c861c6ac2e3eaddf2b4bf8c0bea51` |
| `decision_diff.csv` | Before/after decision diff vs `v1.0.2` | `585d8aa7e35b7eebacb5ec58beeaee5dfc6ca592bb83bf018be18c991fdf5fb3` |
| `excluded_observations.csv` | Explicit exclusion evidence (`64` rows) | `18ed0e862b7e78d3d8bb1b07745a2fa881197db42537f1118351ff938ce88db1` |
| `low_price_review_decisions.csv` | Manual review ledger (`20` rows) | `a804cae42ff3bfbbbfbe12674e1d1375d31caae98357f8646b9fe50ca96ec197` |
| `ml_dataset_manifest.json` | Cryptographic JSON manifest | `f73449339e7ca85bc39031ccecdb3bc64aebe64ef2436d4ad396a94fbe87bbcf` |
| `RELEASE_SIGNOFF.md` | Final signoff document | N/A |

---

## 7. Known Limitations

- **Snapshot Nature:** The dataset is a product-listing snapshot obtained from a frozen search/retrieval configuration during the documented crawl period. It is not an exhaustive catalog of all laptop transactions on Tokopedia.
- **Seller Self-Reporting:** Listing titles, prices, ratings, and review counts reflect seller self-reported metadata on Tokopedia at the time of scraping.

---

## 8. Downstream Publication Boundary

This repository's implementation scope ends at dataset production, validation, and immutable tagging (`ML_DATASET_V1_FINAL`). Preprocessing, scaling, clustering experiments, and Kaggle publication/dataset card setup are handled in separate downstream workflows using this frozen release artifact.
