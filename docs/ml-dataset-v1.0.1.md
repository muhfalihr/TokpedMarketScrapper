# Tokopedia Laptop ML Dataset v1.0.1 Hardening & Freeze Report

> **Dataset Version:** `ml-dataset-v1.0.1` (supersedes candidate `v1.0`)  
> **Source Run ID:** `20260823T043405Z-2m8c6r37` (smoke-250)  
> **Acquisition Tag:** `dataset-acquisition-v1.0`  
> **Git Commit:** `785e6a6b7418eb8cc6074b53b714f443630aaf34`  
> **Hardening Status:** `ML_FREEZE_SEMANTIC_CLASSIFIER_HARDENED`  

---

## 1. Incident Root Cause & Hardening Resolution

During candidate freeze `v1.0` verification, a false-positive classification defect was identified:
- **Root Cause:** Unsafe generic substring matching (e.g. `"dp" in normalized_title`) caused terms inside unrelated brand names, warranty terms, SKUs, and colors to trigger false exclusions.
  - `"IdeaPad"` contains `dp` (`i-d-e-a-p-a-d`) $\rightarrow$ false exclusion as `DOWN_PAYMENT_OR_DEPOSIT`.
  - `"ADP"` / `"2ADP"` / `"3ADP"` (Accidental Damage Protection) $\rightarrow$ false exclusion as `DOWN_PAYMENT_OR_DEPOSIT`.
  - `"NX.DPESN.001"` (SKU identifier) $\rightarrow$ false exclusion as `INVALID_PRICE_REPRESENTATION`.
  - `"Seashell"` (color name) $\rightarrow$ false exclusion as `NON_LAPTOP_COMPONENT` (`shell`).
  - `"Backlit Keyboard"` / `"RGB Keyboard"` (specifications) $\rightarrow$ false exclusion as `NON_LAPTOP_COMPONENT` (`keyboard`).
  - `"Touch LCD"` (display spec) $\rightarrow$ false exclusion as `NON_LAPTOP_COMPONENT` (`lcd`).
  - `"+ Sleeve"` (included laptop gift bundle) $\rightarrow$ false exclusion as `NON_LAPTOP_ACCESSORY` (`sleeve`).

- **Resolution:** Replaced generic substring matchers with boundary-aware token rules (e.g. `(?<![a-z0-9])dp(?![a-z0-9])`), product-head context detection, and strong laptop identity recognition. 
- **Fixtures:** 8 real false-positive cases and 8 true-positive exclusion cases were locked as automated regression fixtures in `tests/fixtures/ml_freeze/`.

---

## 2. Before / After Dataset Comparison

| Metric / Category | Candidate `v1.0` | Corrected `v1.0.1` | Net Change |
| :--- | :--- | :--- | :--- |
| **Total Source Acquisition Rows** | **2,227** | **2,227** | **0 (Immutable)** |
| **Semantically Valid Laptops** | **2,033** | **2,204** | **+171 recovered** |
| **Excluded Observations** | **194** | **23** | **-171 false positives** |
| — Down Payment / Deposit List Price | 111 | 0 | -111 |
| — Non-Laptop Component | 63 | 20 | -43 |
| — Invalid Price Representation | 15 | 0 | -15 |
| — Non-Laptop Accessory | 5 | 3 | -2 |
| **Ambiguous Observations** | **0** | **0** | **0** |
| **Primary Matrix R1 (`price + rating`)** | **1,974** | **2,141** | **+167 complete cases** |
| **Secondary Matrix R2 (`price + rating + review_count`)** | **1,518** | **1,623** | **+105 complete cases** |

---

## 3. Review Count Semantics (Unchanged)

| Semantic Status | Count | Treatment |
| :--- | :--- | :--- |
| **Observed Positive Count** (`> 0`) | 1,266 | Preserved verbatim |
| **Explicit Zero** (`= 0`) | 372 | Preserved verbatim |
| **Semantic Zero Proven** | 0 | None proven |
| **Missing / Unresolved Null** | 589 | Preserved as null (`KEEP_MISSING`), complete cases only in R2 |

---

## 4. Final Remaining Exclusions Audit (23 Rows)

All 23 remaining exclusions were manually audited and verified to be 100% genuine component/accessory items:
- **Component Exclusions (20 rows):** 17 replacement LCD screens (e.g. `Layar LCD LED Laptop Asus S500...`), 1 flex cable (`Kabel Fleksibel LCD...`), 1 laptop shell (`Laptop Shell For Lenovo...`), 1 replacement keyboard (`Keyborad laptop lenovo thinkpad...`).
- **Accessory Exclusions (3 rows):** 2 Intel Ultrabook sticker packs (`Stiker Intel Ultrabook Black/Blue`), 1 standalone laptop sleeve case (`Acer Sleevecase Laptop Original`).

---

## 5. Artifact Verification & Hashes

| Artifact File | Description | SHA-256 Hash |
| :--- | :--- | :--- |
| `r1_price_rating.parquet` | R1 feature matrix | `66d16eda5335798ccbcf38b7ab6244de8ffebc65d5aee2d4855c0f5881259505` |
| `r2_price_rating_review_count.parquet` | R2 feature matrix | `c74f89bd43dd40ac1c03b5ec00d100e8511804bdba13e7e68c93f5a43e724d3e` |
| `cleaning_decisions.csv` | Full audit decision ledger | `0ca97d99cb933b76e96212b58f77498041bc103794a2cdea819bb62fbe34c507` |
| `decision_diff.csv` | Before/after decision diff | `b8fb7b9933c04245aa564e9a8f4c6e93fa282b812efd978a632aefceec1057e0` |
| `excluded_observations.csv` | Explicit exclusion evidence | `acfee76cd407a3def3b409c87af4bd5928a9066597529183ca6cbf38bc54512c` |
| `ambiguous_observations.csv` | Unresolved ambiguous cases | `d0ee0752e3f344d2beb830cb9d2175071684593e58d1113f174269cc80a2ff92` |
| `ml_dataset_manifest.json` | Cryptographic JSON manifest | `845515931df4e299b098cf12ec9da6e96559968c33ea46a233557a1235438275` |

---

## 6. Research Exit Gate Checklist

1. **What exact matcher caused ADP/IdeaPad to be interpreted as DP?** Generic `term in normalized_title` matched `dp` substring inside `ideapad` and `adp`.
2. **Can `ADP`, `2ADP`, `3ADP`, and `NX.DPESN.001` trigger DP exclusion?** **NO**.
3. **Can `Seashell` trigger shell exclusion?** **NO**.
4. **Can `Backlit Keyboard` / `RGB Keyboard` trigger keyboard component exclusion?** **NO**.
5. **Can `Touch LCD` trigger LCD replacement screen exclusion?** **NO**.
6. **Can `+ Sleeve` bundle trigger sleeve accessory exclusion?** **NO**.
7. **Are actual keyboard docking, LCD panel, laptop shell, sleevecase, cable listings still excluded?** **YES**.
8. **Does any price magnitude threshold decide eligibility?** **NO**.
9. **Did review_count missing semantics change?** **NO**.
10. **Are all 2,227 source listings accounted for by exactly one cleaning decision?** **YES**.
11. **Were every revised exclusion and changed decision reviewed?** **YES** (171 changed decisions audited, all 23 remaining exclusions verified).
12. **Corrected R1 row count:** `2,141`
13. **Corrected R2 row count:** `1,623`
14. **Do Parquet hashes match manifest?** **YES**.
15. **Is acquisition source unchanged?** **YES**.
16. **Is corrected freeze tagged immutably?** **YES** (`ml-dataset-v1.0.1`).

---

## 7. Research Handoff Status

$$\text{Phase Exit Status} = \mathbf{ML\_FREEZE\_SEMANTIC\_CLASSIFIER\_HARDENED}$$

The dataset is hardened, cryptographically verified, and tagged as **`ml-dataset-v1.0.1`**. Preprocessing and comparative clustering experiments (StandardScaler, MinMaxScaler, RobustScaler, K-Means, Agglomerative, GMM) can now proceed on corrected `R1` (`2,141` rows) and `R2` (`1,623` rows).
