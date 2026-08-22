"""Tests for the CLI."""

from typer.testing import CliRunner

from laptop_market_scraper.cli import app


runner = CliRunner()


def test_crawl_command_exists():
    result = runner.invoke(app, ["crawl", "--help"])

    assert result.exit_code == 0
    assert "--crawl-dir" in result.stdout
    assert "--max-items" in result.stdout
    assert "--browser-fallback" in result.stdout
