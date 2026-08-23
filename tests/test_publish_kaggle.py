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
