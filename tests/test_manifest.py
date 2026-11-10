"""Tests for reproducibility manifest generation."""

import json
from datetime import UTC, datetime
from pathlib import Path

from tokped_market_scrapper.manifest import generate_manifest, write_manifest


def test_generate_manifest_contains_required_contract_details():
    started_at = datetime(2026, 8, 23, 10, 0, 0, tzinfo=UTC)
    finished_at = datetime(2026, 8, 23, 10, 30, 0, tzinfo=UTC)

    manifest_data = generate_manifest(
        started_at=started_at,
        finished_at=finished_at,
        seed_queries=["laptop", "laptop gaming"],
        observed_total_data_min=100,
        observed_total_data_max=5000,
    )

    assert manifest_data["search_operation"] == "searchProductV5"
    assert "search_contract_sha256" in manifest_data
    assert manifest_data["search_rows"] == 60
    assert manifest_data["search_category_sc"] == "297"
    assert manifest_data["search_sort_code"] == "23"
    assert manifest_data["seed_queries"] == ["laptop", "laptop gaming"]
    assert manifest_data["observed_total_data_min"] == 100
    assert manifest_data["observed_total_data_max"] == 5000
    assert manifest_data["started_at"] == started_at.isoformat()
    assert manifest_data["finished_at"] == finished_at.isoformat()


def test_write_manifest_exports_json(tmp_path: Path):
    manifest_data = {
        "search_operation": "searchProductV5",
        "search_contract_sha256": "abcdef1234567890",
        "search_rows": 60,
        "search_category_sc": "297",
        "search_sort_code": "23",
        "seed_queries": ["laptop"],
        "observed_total_data_min": 200,
        "observed_total_data_max": 2000,
        "started_at": "2026-08-23T10:00:00+00:00",
        "finished_at": "2026-08-23T10:30:00+00:00",
    }

    out_path = write_manifest(tmp_path, manifest_data)

    assert out_path == tmp_path / "manifest.json"
    assert out_path.exists()
    content = json.loads(out_path.read_text(encoding="utf-8"))
    assert content == manifest_data
