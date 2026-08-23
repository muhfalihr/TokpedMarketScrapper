"""Prepare Kaggle dataset release bundle from frozen ML dataset artifact."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd


def render_kaggle_metadata(dataset_id: str, title: str, subtitle: str, license_name: str = "CC-BY-SA-4.0") -> dict:
    """Render dataset-metadata.json dict for Kaggle API."""
    return {
        "title": title,
        "id": dataset_id,
        "licenses": [{"name": license_name}],
        "subtitle": subtitle,
        "keywords": [
            "indonesia",
            "e-commerce",
            "laptops",
            "market-research",
            "data-cleaning",
            "clustering",
        ],
    }


def render_kaggle_readme(manifest: dict) -> str:
    """Render rich Markdown Dataset Card for Kaggle."""
    artifact = manifest.get("artifact", "ml-dataset-v1.0.3")
    run_id = manifest.get("source_run_id", "unknown")
    source_rows = manifest.get("source_rows", 2227)
    cleaning = manifest.get("cleaning", {})
    r1 = manifest.get("representations", {}).get("R1", {})
    r2 = manifest.get("representations", {}).get("R2", {})
    review = manifest.get("release_review", {})

    return f"""# Tokopedia Laptop Market Dataset (2026)

> **Dataset Version:** `{artifact}`  
> **License:** Creative Commons Attribution-ShareAlike 4.0 International (`CC-BY-SA-4.0`)  
> **Source Run ID:** `{run_id}`  
> **Source Accounting:** `{source_rows}` total search listings ingested  
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
| `r1_price_rating.csv` / `.parquet` | Tabular | `{r1.get('rows', 2106)}` | Primary representation R1 (`price`, `rating`) complete cases |
| `r2_price_rating_review_count.csv` / `.parquet` | Tabular | `{r2.get('rows', 1588)}` | Secondary representation R2 (`price`, `rating`, `review_count`) complete cases |
| `cleaning_decisions.csv` | CSV | `{source_rows}` | Complete 12-column audit decision ledger for every listing |
| `excluded_observations.csv` | CSV | `{cleaning.get('excluded_count', 64)}` | Explicit non-laptop component/accessory exclusion evidence |
| `low_price_review_decisions.csv` | CSV | `{review.get('low_price_review_required', 20)}` | Audited low-price (< Rp2,000,000) manual review queue |
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

- **Source Run ID:** `{run_id}`
- **Source Acquisition Tag:** `dataset-acquisition-v1.0`
- **R1 Parquet SHA-256:** `{r1.get('sha256', '')}`
- **R2 Parquet SHA-256:** `{r2.get('sha256', '')}`

---

## 6. Limitations

- The dataset is a search-result snapshot from a frozen Tokopedia crawl configuration.
- Prices, ratings, and review counts reflect self-reported seller metadata on Tokopedia at scrape time.
"""


def prepare_kaggle_release(
    source_dir: Path,
    output_dir: Path,
    dataset_id: str = "muhfalihr/tokopedia-laptop-market-dataset",
    title: str = "Tokopedia Laptop Market Dataset (2026)",
    subtitle: str = "Cleaned, audited, and semantically reconciled dataset of Tokopedia laptop search listings",
    license_name: str = "CC-BY-SA-4.0",
) -> Path:
    """Prepare Kaggle dataset release files in output_dir."""
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = source_dir / "ml_dataset_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found at {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Convert Parquet files to CSV
    r1_parquet = source_dir / "r1_price_rating.parquet"
    if r1_parquet.exists():
        shutil.copy(r1_parquet, output_dir / "r1_price_rating.parquet")
        df_r1 = pd.read_parquet(r1_parquet)
        df_r1.to_csv(output_dir / "r1_price_rating.csv", index=False)

    r2_parquet = source_dir / "r2_price_rating_review_count.parquet"
    if r2_parquet.exists():
        shutil.copy(r2_parquet, output_dir / "r2_price_rating_review_count.parquet")
        df_r2 = pd.read_parquet(r2_parquet)
        df_r2.to_csv(output_dir / "r2_price_rating_review_count.csv", index=False)

    # Copy CSV & JSON files
    for filename in [
        "cleaning_decisions.csv",
        "excluded_observations.csv",
        "low_price_review_decisions.csv",
        "ml_dataset_manifest.json",
    ]:
        src = source_dir / filename
        if src.exists():
            shutil.copy(src, output_dir / filename)

    # Render Kaggle metadata
    meta = render_kaggle_metadata(dataset_id=dataset_id, title=title, subtitle=subtitle, license_name=license_name)
    (output_dir / "dataset-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Render Kaggle Dataset Card README
    readme_content = render_kaggle_readme(manifest)
    (output_dir / "README.md").write_text(readme_content, encoding="utf-8")

    print(f"Kaggle release bundle prepared at: {output_dir}")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Kaggle Dataset Release Bundle")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("data/ml/smoke-250/ml-dataset-v1.0.3"),
        help="Source frozen dataset directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("kaggle/release/v1.0.3"),
        help="Target Kaggle release directory",
    )
    parser.add_argument(
        "--dataset-id",
        type=str,
        default="muhfalihr/tokopedia-laptop-market-dataset",
        help="Kaggle dataset ID (username/slug)",
    )
    args = parser.parse_args()

    prepare_kaggle_release(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        dataset_id=args.dataset_id,
    )


if __name__ == "__main__":
    main()
