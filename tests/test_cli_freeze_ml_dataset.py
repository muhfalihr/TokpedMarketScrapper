"""Tests for freeze-ml-dataset CLI command (Task 12)."""

from typer.testing import CliRunner

from laptop_market_scraper.cli import app

runner = CliRunner()


def test_freeze_ml_dataset_command_exists():
    result = runner.invoke(app, ["freeze-ml-dataset", "--help"])

    assert result.exit_code == 0
    assert "--run-id" in result.stdout
    assert "--config" in result.stdout
    assert "--dry-run" in result.stdout


def test_freeze_command_fails_on_missing_run_id():
    result = runner.invoke(app, ["freeze-ml-dataset"])

    assert result.exit_code != 0
