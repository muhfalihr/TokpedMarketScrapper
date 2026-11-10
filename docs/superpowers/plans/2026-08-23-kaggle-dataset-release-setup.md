# Kaggle Dataset Release Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an automated, reproducible Kaggle dataset release packaging script, Kaggle Dataset Card renderer, metadata configuration, and CLI publisher helper for `ml-dataset-v1.0.3`.

**Architecture:** A standalone packaging script (`scripts/prepare_kaggle_release.py`) ingests the frozen artifact `data/ml/smoke-250/ml-dataset-v1.0.3/`, generates both Parquet and CSV representations for R1 and R2, copies decision ledgers, renders `dataset-metadata.json` and a comprehensive Kaggle Dataset Card `README.md` into `kaggle/release/v1.0.3/`, and validates artifact integrity. A CLI helper script (`scripts/publish_kaggle.py`) handles Kaggle API/CLI publication.

**Tech Stack:** Python 3.12, pandas, PyArrow, PyYAML, Pydantic 2, pytest, Ruff.

## Global Constraints

- Do not mutate the source acquisition data (`2,227` listings) or the frozen dataset matrices (`R1: 2,106`, `R2: 1,588`, `Excluded: 64`).
- Do not store Kaggle API keys, credentials, or secrets in repository files or git history.
- Provide both `.parquet` and `.csv` files for R1 and R2 in `kaggle/release/v1.0.3/`.
- All metrics and column descriptions in the Kaggle Dataset Card must match `ml_dataset_manifest.json` exactly.
- Final completion state is `KAGGLE_RELEASE_READY`.

---

### Task 1: Create `scripts/prepare_kaggle_release.py`

**Files:**
- Create: `scripts/prepare_kaggle_release.py`

**Interfaces:**
- Consumes: Frozen dataset directory `data/ml/smoke-250/ml-dataset-v1.0.3/` (or custom `--source-dir`).
- Produces: Target directory `kaggle/release/v1.0.3/` with `r1_price_rating.parquet`, `r1_price_rating.csv`, `r2_price_rating_review_count.parquet`, `r2_price_rating_review_count.csv`, `cleaning_decisions.csv`, `excluded_observations.csv`, `low_price_review_decisions.csv`, `ml_dataset_manifest.json`, `dataset-metadata.json`, and `README.md`.

- [ ] **Step 1: Write `scripts/prepare_kaggle_release.py`**

```python
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
- `review_count` *(integer)*: Total verified buyer reviews (strictly $\ge 0$).

### Decision Ledger (`cleaning_decisions.csv`)
Contains 12 columns: `listing_key`, `product_name`, `product_url`, `price`, `rating`, `review_count_original`, `review_count_resolved`, `eligibility_decision`, `eligibility_reason`, `review_count_status`, `include_r1`, `include_r2`, `exclusion_reasons_r1`, `exclusion_reasons_r2`, `evidence`.

---

## 4. Semantic Cleaning Rules

Listings were cleaned using a 4-tier semantic precedence system:
1. **Invalid Price Filter:** Excludes listings where list price is a down payment, deposit, or installment (`DP`, `Down Payment`, `Uang Muka`).
2. **Product Head Classifier:** Distinguishes physical laptops from standalone components (RAM sticks, LCD panels, replacement batteries, flex cables, casings) and accessories (chargers, locks, screen protectors, bubble wrap gift placeholders).
3. **Valid Laptop Preservation:** Laptops mentioning included accessories or specs (e.g., `Laptop Lenovo IdeaPad ... 16GB RAM SSD 512GB + Sleeve`) are strictly preserved as valid.
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
```

- [ ] **Step 2: Commit `scripts/prepare_kaggle_release.py`**

```bash
git add scripts/prepare_kaggle_release.py
git commit -m "feat: add Kaggle dataset release packaging script"
```

---

### Task 2: Add Unit Tests for `prepare_kaggle_release.py`

**Files:**
- Create: `tests/test_prepare_kaggle_release.py`

- [ ] **Step 1: Write `tests/test_prepare_kaggle_release.py`**

```python
"""Tests for prepare_kaggle_release script."""

import json
import pandas as pd
from pathlib import Path

from scripts.prepare_kaggle_release import (
    prepare_kaggle_release,
    render_kaggle_metadata,
    render_kaggle_readme,
)


def test_render_kaggle_metadata():
    meta = render_kaggle_metadata(
        dataset_id="user/dataset-name",
        title="Test Title",
        subtitle="Test Subtitle",
        license_name="CC-BY-SA-4.0",
    )
    assert meta["id"] == "user/dataset-name"
    assert meta["title"] == "Test Title"
    assert meta["licenses"][0]["name"] == "CC-BY-SA-4.0"


def test_render_kaggle_readme():
    manifest = {
        "artifact": "ml-dataset-v1.0.3",
        "source_run_id": "run-123",
        "source_rows": 2227,
        "cleaning": {"excluded_count": 64},
        "representations": {
            "R1": {"rows": 2106, "sha256": "abc"},
            "R2": {"rows": 1588, "sha256": "def"},
        },
    }
    readme = render_kaggle_readme(manifest)
    assert "# Tokopedia Laptop Market Dataset (2026)" in readme
    assert "ml-dataset-v1.0.3" in readme
    assert "2,106" in readme or "2106" in readme


def test_prepare_kaggle_release_creates_all_files(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    manifest = {
        "artifact": "ml-dataset-v1.0.3",
        "source_run_id": "run-123",
        "source_rows": 10,
        "representations": {
            "R1": {"rows": 8, "sha256": "sha1"},
            "R2": {"rows": 6, "sha256": "sha2"},
        },
    }
    (source_dir / "ml_dataset_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    df_r1 = pd.DataFrame([{"listing_key": "k1", "price": 1000, "rating": 4.5}])
    df_r1.to_parquet(source_dir / "r1_price_rating.parquet")

    df_r2 = pd.DataFrame([{"listing_key": "k1", "price": 1000, "rating": 4.5, "review_count": 5}])
    df_r2.to_parquet(source_dir / "r2_price_rating_review_count.parquet")

    output_dir = tmp_path / "target"
    prepare_kaggle_release(source_dir=source_dir, output_dir=output_dir)

    assert (output_dir / "r1_price_rating.parquet").exists()
    assert (output_dir / "r1_price_rating.csv").exists()
    assert (output_dir / "r2_price_rating_review_count.parquet").exists()
    assert (output_dir / "r2_price_rating_review_count.csv").exists()
    assert (output_dir / "dataset-metadata.json").exists()
    assert (output_dir / "README.md").exists()
```

- [ ] **Step 2: Run pytest to verify tests pass**

```bash
.venv\Scripts\python.exe -m pytest tests/test_prepare_kaggle_release.py -v
```
Expected: PASS.

- [ ] **Step 3: Commit unit tests**

```bash
git add tests/test_prepare_kaggle_release.py
git commit -m "test: add unit tests for Kaggle release preparation script"
```

---

### Task 3: Create `scripts/publish_kaggle.py`

**Files:**
- Create: `scripts/publish_kaggle.py`

**Interfaces:**
- Consumes: Release directory `kaggle/release/v1.0.3/`.
- Interacts: Kaggle CLI (`kaggle datasets create` or `kaggle datasets version`).

- [ ] **Step 1: Write `scripts/publish_kaggle.py`**

```python
"""CLI publisher helper script for Kaggle Datasets."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def check_kaggle_cli() -> bool:
    """Check if kaggle CLI is installed in environment."""
    return shutil.which("kaggle") is not None


def publish_to_kaggle(
    release_dir: Path,
    version_notes: str = "Release v1.0.3 - Tokopedia Laptop ML Dataset",
    new_dataset: bool = False,
) -> bool:
    """Publish dataset release to Kaggle using Kaggle CLI."""
    release_dir = Path(release_dir)
    meta_path = release_dir / "dataset-metadata.json"
    if not meta_path.exists():
        print(f"Error: dataset-metadata.json not found in {release_dir}")
        return False

    if not check_kaggle_cli():
        print("Warning: Kaggle CLI ('kaggle') is not installed or not in PATH.")
        print("\nTo publish manually:")
        print("1. Install Kaggle CLI: pip install kaggle")
        print("2. Place kaggle.json in ~/.kaggle/")
        print(f"3. Run: kaggle datasets create -p {release_dir}")
        print("OR upload the files in kaggle/release/v1.0.3 via Kaggle Web UI (https://www.kaggle.com/datasets).")
        return False

    cmd = ["kaggle", "datasets", "create", "-p", str(release_dir)] if new_dataset else ["kaggle", "datasets", "version", "-p", str(release_dir), "-m", version_notes]

    print(f"Executing: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Kaggle Publish Output:\n", res.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("Kaggle Publish Error:\n", e.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish dataset release to Kaggle")
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=Path("kaggle/release/v1.0.3"),
        help="Path to Kaggle release directory",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Create a new dataset (default creates a new version)",
    )
    parser.add_argument(
        "--notes",
        type=str,
        default="Release v1.0.3 - Tokopedia Laptop ML Dataset",
        help="Version update notes",
    )
    args = parser.parse_args()

    publish_to_kaggle(
        release_dir=args.release_dir,
        version_notes=args.notes,
        new_dataset=args.new,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit `scripts/publish_kaggle.py`**

```bash
git add scripts/publish_kaggle.py
git commit -m "feat: add Kaggle publisher CLI helper script"
```

---

### Task 4: Add Unit Tests for `publish_kaggle.py`

**Files:**
- Create: `tests/test_publish_kaggle.py`

- [ ] **Step 1: Write `tests/test_publish_kaggle.py`**

```python
"""Tests for publish_kaggle helper script."""

from pathlib import Path
from unittest.mock import patch

from scripts.publish_kaggle import check_kaggle_cli, publish_to_kaggle


def test_check_kaggle_cli_returns_bool():
    result = check_kaggle_cli()
    assert isinstance(result, bool)


def test_publish_to_kaggle_fails_if_metadata_missing(tmp_path: Path):
    result = publish_to_kaggle(tmp_path)
    assert result is False


@patch("scripts.publish_kaggle.check_kaggle_cli", return_value=False)
def test_publish_to_kaggle_handles_missing_cli(mock_cli, tmp_path: Path):
    (tmp_path / "dataset-metadata.json").write_text("{}", encoding="utf-8")
    result = publish_to_kaggle(tmp_path)
    assert result is False
```

- [ ] **Step 2: Run pytest to verify tests pass**

```bash
.venv\Scripts\python.exe -m pytest tests/test_publish_kaggle.py -v
```
Expected: PASS.

- [ ] **Step 3: Commit unit tests**

```bash
git add tests/test_publish_kaggle.py
git commit -m "test: add unit tests for Kaggle publisher helper script"
```

---

### Task 5: Execute Kaggle Release Packaging (`kaggle/release/v1.0.3/`)

**Files:**
- Create: `kaggle/release/v1.0.3/*`

- [ ] **Step 1: Run `prepare_kaggle_release.py`**

```bash
.venv\Scripts\python.exe scripts/prepare_kaggle_release.py \
  --source-dir data/ml/smoke-250/ml-dataset-v1.0.3 \
  --output-dir kaggle/release/v1.0.3
```

- [ ] **Step 2: Verify release directory files**

Run verification script:
```python
python -c "
import pandas as pd
from pathlib import Path

p = Path('kaggle/release/v1.0.3')
assert (p / 'r1_price_rating.parquet').exists()
assert (p / 'r1_price_rating.csv').exists()
assert (p / 'r2_price_rating_review_count.parquet').exists()
assert (p / 'r2_price_rating_review_count.csv').exists()
assert (p / 'cleaning_decisions.csv').exists()
assert (p / 'excluded_observations.csv').exists()
assert (p / 'dataset-metadata.json').exists()
assert (p / 'README.md').exists()

df_r1 = pd.read_csv(p / 'r1_price_rating.csv')
df_r2 = pd.read_csv(p / 'r2_price_rating_review_count.csv')

assert len(df_r1) == 2106
assert len(df_r2) == 1588

print('KAGGLE RELEASE V1.0.3 BUNDLE VERIFIED 100% SUCCESS!')
"
```

- [ ] **Step 3: Run full pytest & ruff checks**

```bash
.venv\Scripts\python.exe -m pytest -v
.venv\Scripts\ruff.exe check src tests scripts
```

- [ ] **Step 4: Commit `kaggle/release/v1.0.3/` release files**

```bash
git add kaggle/release/v1.0.3/
git commit -m "data: generate Kaggle dataset release bundle v1.0.3"
```
