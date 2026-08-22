"""Command-line interface for the Tokopedia Laptop Scraper."""

import json
import random
import string
from datetime import UTC, datetime
from pathlib import Path

import typer

from laptop_market_scraper.quality import build_quality_report
from laptop_market_scraper.spiders.tokopedia_laptop import TokopediaLaptopSpider
from laptop_market_scraper.storage import SQLiteStore

app = typer.Typer(help="Tokopedia Laptop Research Dataset Crawler")


def _generate_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{timestamp}-{random_str}"


@app.command()
def crawl(
    seed_config: Path = typer.Option("config/seeds.yaml", help="Path to seed configuration"),
    crawl_dir: Path = typer.Option("crawl_state/tokopedia_laptop", help="Directory for crawl state and database"),
    max_items: int = typer.Option(None, help="Maximum number of items to crawl"),
    max_pages: int = typer.Option(None, help="Maximum number of pages to crawl per seed"),
    browser_fallback: bool = typer.Option(False, help="Use browser fallback for dynamic content"),
):
    """Run the Scrapling crawler to collect laptop data."""
    run_id = _generate_run_id()

    crawl_dir.mkdir(parents=True, exist_ok=True)
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    spider = TokopediaLaptopSpider(
        crawl_run_id=run_id,
        store=store,
        seed_config=str(seed_config),
        max_items=max_items,
        max_pages=max_pages,
        browser_fallback=browser_fallback,
    )

    spider.start()

@app.command()
def export(
    run_id: str = typer.Option(..., help="Crawl run ID to export"),
    crawl_dir: Path = typer.Option("crawl_state/tokopedia_laptop", help="Directory containing crawl database"),
    output_dir: Path = typer.Option("data/processed", help="Directory for processed exports"),
):
    """Export the crawled data to CSV and Parquet formats."""
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    run_out_dir = output_dir / run_id
    csv_path = run_out_dir / "laptops.csv"
    parquet_path = run_out_dir / "laptops.parquet"

    store.export_processed(csv_path, parquet_path)
    print(f"Exported to {csv_path} and {parquet_path}")


@app.command()
def quality(
    run_id: str = typer.Option(..., help="Crawl run ID to evaluate"),
    crawl_dir: Path = typer.Option("crawl_state/tokopedia_laptop", help="Directory containing crawl database"),
    report_dir: Path = typer.Option("reports", help="Directory for quality reports"),
):
    """Generate a quality report for a specific crawl run."""
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    report = build_quality_report(run_id, store)

    run_report_dir = report_dir / run_id
    run_report_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_report_dir / "quality.json"
    json_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")

    md_path = run_report_dir / "quality.md"
    md_content = f"# Quality Report: {run_id}\n\n"
    for k, v in report.model_dump().items():
        md_content += f"- **{k}**: {v}\n"
    md_path.write_text(md_content, encoding="utf-8")

    print(f"Quality reports written to {json_path} and {md_path}")


@app.command()
def inspect(
    run_id: str = typer.Option(..., help="Crawl run ID to inspect"),
    crawl_dir: Path = typer.Option("crawl_state/tokopedia_laptop", help="Directory containing crawl database"),
):
    """Inspect basic stats for a given crawl run."""
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    count = store.count_products(run_id=run_id)
    rejected = store.count_rejected(run_id=run_id)

    print(f"Run ID: {run_id}")
    print(f"Products: {count}")
    print(f"Rejected: {rejected}")


if __name__ == "__main__":
    app()
