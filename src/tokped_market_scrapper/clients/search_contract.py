"""GraphQL Search Contract domain model and loader for Tokopedia searchProductV5 migration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field


class SearchContract(BaseModel):
    """Pydantic model representing a frozen GraphQL search contract."""

    operation_name: str = Field(description="GraphQL operation name")
    query: str = Field(description="Exact captured GraphQL query document string")
    sha256: str = Field(min_length=64, max_length=64, description="SHA-256 hash of exact query string")


def load_search_contract(path: Path | str) -> SearchContract:
    """Load search contract JSON from path and verify SHA-256 hash integrity.

    Args:
        path: Path to search contract JSON file.

    Returns:
        SearchContract instance.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If SHA-256 hash does not match computed query hash.
        ValidationError: If JSON schema does not conform to SearchContract model.
    """
    contract_path = Path(path)
    if not contract_path.is_file():
        raise FileNotFoundError(f"Contract file not found: {contract_path}")

    raw_text = contract_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)

    contract = SearchContract.model_validate(data)

    computed_sha256 = hashlib.sha256(contract.query.encode("utf-8")).hexdigest()
    if contract.sha256 != computed_sha256:
        raise ValueError(
            f"SHA-256 hash mismatch in search contract {contract_path}: "
            f"expected {contract.sha256}, computed {computed_sha256}"
        )

    return contract
