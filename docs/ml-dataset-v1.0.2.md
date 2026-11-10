# Tokopedia Laptop ML Dataset v1.0.2 Final Freeze & Product-Head Hardening Report

> **Dataset Version:** `ml-dataset-v1.0.2` (Final ML Freeze)  
> **Source Run ID:** `20260823T043405Z-2m8c6r37` (smoke-250)  
> **Acquisition Tag:** `dataset-acquisition-v1.0`  
> **Git Commit:** `fcd6a5710c2e5bba5a0c188d8492f8a6dabf191d`  
> **Final Phase Handoff Status:** `ML_DATASET_V1_FINAL`  

---

## 1. Incident Root Cause & Hardening Resolution

Following candidate freeze `v1.0.1`, a audit of `VALID_LAPTOP` rows exposed a secondary defect: **product-head false-negative leakage**.
- **Problem:** Certain non-laptop products (RAM modules, power adapters, replacement batteries, flex cables, security locks, paper notebooks, and bonus/gift placeholders) contained generic computer words like `laptop`, `notebook`, or `ultrabook` (e.g. `KABEL POWER FOR NOTEBOOK`, `RAM LAPTOP SODIMM DDR5`, `Daiichi Pop Notebook A5`, `Bonus Pembelian Laptop Lenovo ... - Bubble Wrap`). Generic brand/category identity previously overrode product-head identity, allowing these non-laptop items to survive into the valid dataset.
- **Resolution:**
  1. Created explicit `classify_product_head()` function to extract the primary product identity (`LAPTOP`, `COMPONENT`, `ACCESSORY`, `PAPER_NOTEBOOK`, `PLACEHOLDER`, `UNKNOWN`).
  2. Prioritized primary product head identity over generic laptop brand/category keywords in semantic precedence.
  3. Preserved valid laptop listings that merely mention specifications (RAM, SSD, battery, LCD) or bundle items.
  4. Added `low_price_review.csv` as a diagnostic-only queue for laptops priced below Rp2,000,000 to facilitate 100% human review without using price as an automated exclusion rule.
  5. Added production-derived regression fixtures in `tests/fixtures/ml_freeze/`.

---

## 2. Before / After Dataset Comparison Across Versions

| Metric / Category | Candidate `v1.0` | Hardened `v1.0.1` | Final `v1.0.2` | Net Change (v1.0.1 $\rightarrow$ v1.0.2) |
| :--- | :--- | :--- | :--- | :--- |
| **Total Source Acquisition Rows** | **2,227** | **2,227** | **2,227** | **0 (Immutable)** |
| **Semantically Valid Laptops** | **2,033** | **2,204** | **2,163** | **-41 non-laptop leakage removed** |
| **Excluded Observations** | **194** | **23** | **64** | **+41 non-laptop leakage caught** |
| — Down Payment / Deposit List Price | 111 | 0 | 0 | 0 |
| — Non-Laptop Component | 63 | 20 | 29 | +9 |
| — Invalid Price Representation | 15 | 0 | 0 | 0 |
| — Non-Laptop Accessory | 5 | 3 | 33 | +30 |
| — Non-Laptop Other (Stationery) | 0 | 0 | 2 | +2 |
| **Ambiguous Observations** | **0** | **0** | **0** | **0** |
| **Primary Matrix R1 (`price + rating`)** | **1,974** | **2,141** | **2,106** | **-35 complete non-laptop cases removed** |
| **Secondary Matrix R2 (`price + rating + review_count`)** | **1,518** | **1,623** | **1,588** | **-35 complete non-laptop cases removed** |

---

## 3. Review Count Semantics (Unchanged)

| Semantic Status | Count | Treatment |
| :--- | :--- | :--- |
| **Observed Positive Count** (`> 0`) | 1,266 | Preserved verbatim |
| **Explicit Zero** (`= 0`) | 372 | Preserved verbatim |
| **Semantic Zero Proven** | 0 | None proven |
| **Missing / Unresolved Null** | 589 | Preserved as null (`KEEP_MISSING`), complete cases only in R2 |

---

## 4. Final Remaining Exclusions Breakdown (64 Rows)

- **Non-Laptop Component (29 rows):** Replacement LCD panels (18), SODIMM RAM modules (2), replacement batteries (2), flex cables (2), SSDs (2), bracket frames (1), replacement keyboards (1), replacement casings/shells (1).
- **Non-Laptop Accessory (33 rows):** Gift bonus placeholders (24), power adapters & chargers (3), security locks (2), screen/keyboard protectors (2), standalone sleeve cases (1), sticker packs (1).
- **Non-Laptop Other (2 rows):** Daiichi Pop Notebook A5 paper stationery notebooks (2).

---

## 5. Artifact Verification & SHA-256 Hashes

| Artifact File | Description | SHA-256 Hash |
| :--- | :--- | :--- |
| `r1_price_rating.parquet` | R1 feature matrix (`2,106` rows) | `00623b78e3ece31c12bb07e4848e85217737effb233a7d2fc1167b7c0eccbe49` |
| `r2_price_rating_review_count.parquet` | R2 feature matrix (`1,588` rows) | `026a6cf8dbda5dee099fa4716d8dbd4c7cf4a490654c68ee6fe380bc913bc9b9` |
| `cleaning_decisions.csv` | Full audit decision ledger | `5da5da47a050ef369ac8f15abcb2e2e1593c861c6ac2e3eaddf2b4bf8c0bea51` |
| `decision_diff.csv` | Before/after decision diff | `585d8aa7e35b7eebacb5ec58beeaee5dfc6ca592bb83bf018be18c991fdf5fb3` |
| `excluded_observations.csv` | Explicit exclusion evidence | `18ed0e862b7e78d3d8bb1b07745a2fa881197db42537f1118351ff938ce88db1` |
| `low_price_review.csv` | Diagnostic low-price queue | `2d409eaac97645ae4ae0d9fef1cdd9ee0ee061803fdcf2fffcbd8fce2d0f507b` |
| `ml_dataset_manifest.json` | Cryptographic JSON manifest | `3fa59936420b7a39b8f9a34059a39fbb9ae0b3b508aed6efdd3d64f51530ca17` |

---

## 6. Research Exit Gate Checklist

1. **Are power cables/adapters/chargers sold as primary product excluded?** **YES**.
2. **Are RAM/SODIMM products excluded?** **YES**.
3. **Are SSD/HDD products sold as primary product excluded?** **YES**.
4. **Are replacement batteries excluded?** **YES**.
5. **Are LCD/display panels, brackets, frames, connectors, and flex cables excluded?** **YES**.
6. **Are security locks and standalone protectors excluded?** **YES**.
7. **Are paper notebooks excluded?** **YES**.
8. **Are bubble-wrap/bonus placeholder listings excluded?** **YES**.
9. **Can a valid laptop still mention RAM, SSD, battery, LCD, keyboard, adapter, sleeve, or bonus items?** **YES**.
10. **Did ADP/DP, Seashell/shell, keyboard-spec, LCD-spec, and sleeve-bundle false-positive fixes remain intact?** **YES**.
11. **Does price < Rp2,000,000 automatically exclude anything?** **NO**.
12. **Were all low-price valid rows manually reviewed?** **YES** (20 valid second/refurbished laptops reviewed in `low_price_review.csv`).
13. **Were all final exclusions manually reviewed?** **YES** (64 rows verified).
14. **Are all 2,227 source listings represented by exactly one cleaning decision?** **YES**.
15. **Did review_count semantics remain unchanged?** **YES**.
16. **Final R1 row count:** `2,106`
17. **Final R2 row count:** `1,588`
18. **Do Parquet SHA-256 values match manifest?** **YES**.
19. **Is source acquisition dataset unchanged?** **YES**.
20. **Is corrected dataset tagged immutably?** **YES** (`ml-dataset-v1.0.2`).

---

## 7. Research Handoff Status

$$\text{Final Research Handoff Status} = \mathbf{ML\_DATASET\_V1\_FINAL}$$

The dataset is fully cleaned, hardened against false positives and false negatives, cryptographically verified, and tagged as **`ml-dataset-v1.0.2`**. Preprocessing and comparative clustering experiments (StandardScaler, MinMaxScaler, RobustScaler, K-Means, Agglomerative, GMM) can now safely begin on final `R1` (`2,106` rows) and `R2` (`1,588` rows).
