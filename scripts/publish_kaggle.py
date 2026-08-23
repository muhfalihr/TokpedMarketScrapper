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
