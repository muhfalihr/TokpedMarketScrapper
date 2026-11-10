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


def test_freeze_cli_exposes_release_closure_inputs():
    result = runner.invoke(app, ["freeze-ml-dataset", "--help"])

    assert result.exit_code == 0
    for option in (
        "--review-decisions",
        "--baseline-decisions",
        "--baseline-artifact",
        "--artifact-version",
    ):
        assert option in result.stdout


def test_strict_freeze_requires_review_decisions():
    result = runner.invoke(
        app,
        [
            "freeze-ml-dataset",
            "--run-id",
            "dummy-run",
            "--strict",
        ],
    )

    assert result.exit_code != 0

