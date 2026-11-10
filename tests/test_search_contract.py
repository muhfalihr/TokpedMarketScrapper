"""Tests for Tokopedia searchProductV5 GraphQL contract loading and hash integrity verification."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tokped_market_scrapper.clients.search_contract import SearchContract, load_search_contract

CONTRACT_PATH = Path("config/search_product_v5_contract.json")


def test_load_search_contract_valid():
    """Verify loading valid search contract returns SearchContract with valid SHA-256."""
    contract = load_search_contract(CONTRACT_PATH)

    assert isinstance(contract, SearchContract)
    assert contract.operation_name == "SearchProductV5Query"
    assert "query SearchProductV5Query" in contract.query
    assert len(contract.sha256) == 64

    # Verify SHA-256 hash match
    expected_hash = hashlib.sha256(contract.query.encode("utf-8")).hexdigest()
    assert contract.sha256 == expected_hash


def test_load_search_contract_file_not_found():
    """Verify loading non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_search_contract(Path("config/non_existent_contract.json"))


def test_load_search_contract_hash_mismatch(tmp_path):
    """Verify contract with tampered query or hash raises ValueError."""
    bad_contract_data = {
        "operation_name": "searchProductV5",
        "query": "query TamperedQuery { searchProductV5 { id } }",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    }
    tampered_file = tmp_path / "tampered_contract.json"
    tampered_file.write_text(json.dumps(bad_contract_data), encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 hash mismatch"):
        load_search_contract(tampered_file)


def test_search_contract_model_validation():
    """Verify SearchContract Pydantic model requires operation_name, query, and sha256."""
    with pytest.raises(ValidationError):
        SearchContract(operation_name="searchProductV5", query="query { foo }")
