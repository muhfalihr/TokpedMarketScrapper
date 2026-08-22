"""Command-line interface for the Tokopedia Laptop Scraper."""

import json
import random
import string
from datetime import UTC, datetime
from pathlib import Path

import typer
from scrapling import Fetcher

from laptop_market_scraper.parsers.listing import parse_listing_page
from laptop_market_scraper.parsers.state import (
    FLIGHT_MARKER,
    _to_adaptor,
    detect_flight_marker,
    extract_state_candidates,
    score_candidates,
)
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


@app.command(name="inspect-listing")
def inspect_listing(
    target: str = typer.Argument(..., help="URL or path to HTML file"),
) -> None:
    """Inspect and diagnose state and DOM extraction for a Tokopedia listing URL or HTML file."""
    is_url = target.startswith(("http://", "https://"))
    status_desc: str
    body_size: int
    response_or_html: object

    if is_url:
        try:
            resp = Fetcher.get(target)
            status_code = getattr(resp, "status", "unknown")
            status_desc = f"HTTP {status_code} ({target})"
            raw_body = getattr(resp, "body", None)
            if isinstance(raw_body, bytes):
                body_size = len(raw_body)
            elif hasattr(resp, "text") and isinstance(resp.text, str):
                body_size = len(resp.text.encode("utf-8", errors="replace"))
            else:
                body_size = len(str(resp).encode("utf-8", errors="replace"))
            response_or_html = resp
        except Exception as exc:
            typer.echo(f"Error fetching URL {target}: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    else:
        path = Path(target)
        if not path.is_file():
            typer.echo(f"Error: File not found: {target}", err=True)
            raise typer.Exit(code=1)
        try:
            raw_bytes = path.read_bytes()
            body_size = len(raw_bytes)
            status_desc = f"File read: {path.resolve()}"
            response_or_html = raw_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            typer.echo(f"Error reading file {target}: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    page = _to_adaptor(response_or_html)
    scripts = page.css("script") if hasattr(page, "css") else []
    total_scripts = len(scripts)
    app_json_count = 0
    for s in scripts:
        attrib = getattr(s, "attrib", {}) or {}
        stype = attrib.get("type", "").strip().lower()
        sid = attrib.get("id", "").strip()
        if stype == "application/json" or sid == "__NEXT_DATA__":
            app_json_count += 1

    # Detect hydration markers
    if isinstance(response_or_html, str):
        html_text = response_or_html
    elif hasattr(response_or_html, "text") and isinstance(response_or_html.text, str):
        html_text = response_or_html.text
    elif hasattr(response_or_html, "body"):
        b = response_or_html.body
        html_text = b.decode("utf-8", errors="replace") if isinstance(b, bytes) else str(b)
    else:
        html_text = str(response_or_html)

    detected_markers: list[str] = []
    if "__NEXT_DATA__" in html_text or any(
        (getattr(s, "attrib", {}) or {}).get("id") == "__NEXT_DATA__" for s in scripts
    ):
        detected_markers.append("__NEXT_DATA__")
    if "__INITIAL_STATE__" in html_text or "window.__INITIAL_STATE__" in html_text:
        detected_markers.append("__INITIAL_STATE__")
    if detect_flight_marker(response_or_html) or "__next_f" in html_text or FLIGHT_MARKER in html_text:
        detected_markers.append("__next_f")

    # State candidates & scoring
    candidates = extract_state_candidates(response_or_html)
    scored_candidates = score_candidates(candidates)

    # Parsing result & diagnostics
    page_data = parse_listing_page(response_or_html)
    diag = page_data.diagnostics

    # Structured output
    typer.echo(f"Source: {status_desc}")
    typer.echo(f"Body size: {body_size} bytes")
    typer.echo(
        f"Scripts summary: {total_scripts} total ({app_json_count} application/json or __NEXT_DATA__)"
    )
    markers_str = ", ".join(detected_markers) if detected_markers else "none"
    typer.echo(f"Detected hydration markers: {markers_str}")
    typer.echo(f"State candidates found: {len(candidates)}")
    for idx, scored in enumerate(scored_candidates):
        cand = scored.candidate
        typer.echo(
            f"  [{idx}] source='{cand.source}', script_idx={cand.script_index}, "
            f"products={scored.product_count}, has_pagination={scored.has_pagination}"
        )
    typer.echo(f"Selected state source: {page_data.state_source or 'None'}")
    typer.echo(f"Product count: {len(page_data.product_urls)}")
    typer.echo(
        f"Pagination summary: current_page={page_data.current_page}, "
        f"next_page={page_data.next_page}, has_next_page={page_data.has_next_page}, "
        f"total_products={page_data.total_products}"
    )
    typer.echo(f"DOM fallback used: {'yes' if page_data.dom_fallback_used else 'no'}")
    typer.echo(
        f"Diagnostics: scripts_scanned={diag.scripts_scanned}, "
        f"candidates={diag.state_candidates_found}, "
        f"json_errors={diag.json_decode_errors}, "
        f"flight_detected={'yes' if diag.next_f_detected else 'no'}, "
        f"records_seen={diag.product_records_seen}, "
        f"accepted={diag.product_urls_accepted}, "
        f"rejected={diag.product_urls_rejected}, "
        f"dom_fallback={'yes' if diag.dom_fallback_used else 'no'}"
    )


if __name__ == "__main__":
    app()

