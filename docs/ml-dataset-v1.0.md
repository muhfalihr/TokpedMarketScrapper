# Tokopedia Laptop ML Dataset v1.0 Freeze Report

> **Dataset Version:** `ml-dataset-v1.0`  
> **Source Run ID:** `20260823T043405Z-2m8c6r37` (smoke-250)  
> **Acquisition Tag:** `dataset-acquisition-v1.0`  
> **Git Commit:** `537d12b494c58a4ca9995b096f7ece9a437bb5e3`  
> **Freeze Status:** `ML_DATASET_V1_FROZEN`  

---

## 1. Overview & Provenance

The audited Tokopedia acquisition dataset (`2,227` rows) has undergone versioned semantic eligibility reconciliation and review count missingness resolution. The processed artifacts are cryptographically hashed and frozen as `ml-dataset-v1.0`.

Source acquisition data remained strictly **immutable**. No missing values were zero-imputed without explicit evidence, no numeric price cutoffs were applied, and valid high-end laptops were fully preserved.

---

## 2. Eligibility & Cleaning Reconciliation Summary

| Metric / Category | Count | Percentage of Source |
| :--- | :--- | :--- |
| **Total Source Acquisition Rows** | **2,227** | **100.0%** |
| **Semantically Valid Laptops** | **2,033** | **91.3%** |
| **Excluded Observations** | **194** | **8.7%** |
| — Down Payment / Deposit List Price | 111 | 5.0% |
| — Non-Laptop Component (LCD, Keyboard, Cable, Shell) | 63 | 2.8% |
| — Invalid Price Representation (Variant/Title Mismatch) | 15 | 0.7% |
| — Non-Laptop Accessory (Charger, Sleeve, Stand) | 5 | 0.2% |
| **Ambiguous Observations** | **0** | **0.0%** |

---

## 3. Review Count Missingness Semantics

| Semantic Status | Count | Policy / Treatment |
| :--- | :--- | :--- |
| **Observed Positive Count** (`> 0`) | 1,266 | Preserved verbatim |
| **Explicit Zero** (`= 0`) | 372 | Preserved verbatim |
| **Semantic Zero Proven** | 0 | None proven |
| **Missing / Unresolved Null** | 589 | Preserved as null (`KEEP_MISSING`), complete cases only in R2 |

---

## 4. Frozen ML Feature Matrices

### Primary Matrix R1: `price + rating`
- **Features:** `["price", "rating"]`
- **Row Count:** **1,974**
- **Retention:** **97.1%** relative to valid laptop universe (59 missing rating rows excluded)
- **Completeness:** 100% complete cases (0 nulls)
- **Parquet Artifact:** `data/ml/smoke-250/ml-dataset-v1.0/r1_price_rating.parquet`
- **SHA-256:** `61abbd690c2a0f966cbb8e6033bfcb78880b201488fe6190da93a15318307b7c`

### Secondary Matrix R2: `price + rating + review_count`
- **Features:** `["price", "rating", "review_count"]`
- **Row Count:** **1,518**
- **Retention:** **74.7%** relative to valid laptop universe (1,266 positive + 372 explicit zero = 1,638 review_count present, minus 120 missing rating = 1,518)
- **Completeness:** 100% complete cases (0 nulls)
- **Parquet Artifact:** `data/ml/smoke-250/ml-dataset-v1.0/r2_price_rating_review_count.parquet`
- **SHA-256:** `157e25ee0676ca17ec3cdc7b6a7fc008731d173e1d65a0f75d02d88fd372744a`

---

## 5. Artifact Verification & Hashes

| Artifact File | Description | SHA-256 Hash |
| :--- | :--- | :--- |
| `r1_price_rating.parquet` | R1 feature matrix | `61abbd690c2a0f966cbb8e6033bfcb78880b201488fe6190da93a15318307b7c` |
| `r2_price_rating_review_count.parquet` | R2 feature matrix | `157e25ee0676ca17ec3cdc7b6a7fc008731d173e1d65a0f75d02d88fd372744a` |
| `cleaning_decisions.csv` | Full audit decision ledger | `b8288958e53ccbeaf5695aa21f7d68d7ac1bc9f95d229e1ed6ee074603cf959f` |
| `excluded_observations.csv` | Explicit exclusion evidence | `2fe3aa6039b6e508a18e59e4535761eddc5768dde87592d5c05687bd2367b087` |
| `ambiguous_observations.csv` | Unresolved ambiguous cases | `d0ee0752e3f344d2beb830cb9d2175071684593e58d1113f174269cc80a2ff92` |
| `ml_dataset_manifest.json` | Full JSON manifest | Read from manifest artifact |

---

## 6. Task 19 Exit Gate Checklist

1. **How many acquisition rows are valid laptops?** `2,033` (91.3%)
2. **How many excluded as accessories/components?** `68` (63 components + 5 accessories)
3. **How many excluded as invalid price representations / DP?** `126` (111 DP/deposit + 15 invalid price)
4. **How many remain ambiguous?** `0`
5. **Were extreme prices deleted solely due to magnitude?** **NO**. High-end valid laptops (up to IDR 189.9M Acer Predator Helios 18 AI & IDR 105.5M ROG Scar 16) remain included.
6. **Are confirmed valid high-end laptops preserved?** **YES**.
7. **Missing-value policy for rating?** No zero imputation; null rating excluded from matrices.
8. **Missing-value policy for review_count?** `KEEP_MISSING`. Complete cases only in R2.
9. **Were null review_count values recoded to zero?** **NO**.
10. **Final R1 row count:** `1,974`
11. **Final R2 row count:** `1,518`
12. **Do R1/R2 contain only complete required features?** **YES**.
13. **Are all excluded rows represented in cleaning ledger?** **YES**.
14. **Does manifest cryptographically identify all artifacts?** **YES**.
15. **Is source acquisition dataset unchanged?** **YES**.

---

## 7. Research Exit Decision

$$\text{Phase Exit Status} = \mathbf{ML\_DATASET\_V1\_FROZEN}$$

The dataset is locked and cryptographically validated. Preprocessing and comparative clustering experiments (StandardScaler, MinMaxScaler, RobustScaler, K-Means, Agglomerative, GMM) may now proceed on `R1` and `R2`.
