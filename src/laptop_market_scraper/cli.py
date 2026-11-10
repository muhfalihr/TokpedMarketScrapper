"""Command-line interface for the Tokopedia Laptop Scraper."""

import random
import string
from datetime import UTC, datetime
from pathlib import Path

import typer
from scrapling import Fetcher

from laptop_market_scraper.audit import (
    FeatureSuitability,
    audit_features,
    export_feature_audit,
)
from laptop_market_scraper.catalog.enrich import CatalogEnrichSpider
from laptop_market_scraper.catalog.spider import CatalogCollectSpider
from laptop_market_scraper.catalog.store import CatalogStore
from laptop_market_scraper.manifest import generate_manifest, write_manifest
from laptop_market_scraper.ml_freeze import freeze_ml_dataset
from laptop_market_scraper.ml_readiness import (
    load_ml_readiness_config,
    run_ml_readiness_audit,
    write_ml_readiness_artifacts,
)
from laptop_market_scraper.parsers.listing import parse_listing_page
from laptop_market_scraper.parsers.state import (
    FLIGHT_MARKER,
    _to_adaptor,
    detect_flight_marker,
    extract_state_candidates,
    score_candidates,
)
from laptop_market_scraper.pipeline import ProductionPipeline
from laptop_market_scraper.quality import export_quality_report, generate_quality_report
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
def catalog_collect(
    seed_config: Path = typer.Option(
        "config/catalog_seeds.yaml", help="Path to multi-category catalog seed configuration"
    ),
    crawl_dir: Path = typer.Option("crawl_state/catalog", help="Directory for catalog crawl state"),
    max_pages: int = typer.Option(None, help="Maximum pages per keyword x tier task"),
    keywords: str = typer.Option(
        None, help="Comma-separated keyword filter (default: all keywords in config)"
    ),
):
    """Collect multi-category products from search (fast, no product page visits)."""
    run_id = _generate_run_id()

    crawl_dir.mkdir(parents=True, exist_ok=True)
    db_path = crawl_dir / "catalog.db"
    store = CatalogStore(db_path, data_dir=crawl_dir)

    keywords_filter = None
    if keywords:
        keywords_filter = tuple(k.strip() for k in keywords.split(",") if k.strip())

    spider = CatalogCollectSpider(
        crawl_run_id=run_id,
        store=store,
        seed_config=str(seed_config),
        max_pages=max_pages,
        keywords_filter=keywords_filter,
    )

    spider.start()

    total = store.count_products(run_id)
    print(f"Collect run {run_id}: {total} unique products saved to {db_path}")


@app.command()
def catalog_enrich(
    crawl_dir: Path = typer.Option("crawl_state/catalog", help="Directory containing catalog database"),
    run_id: str = typer.Option(..., help="Catalog collect run ID to enrich"),
    limit: int = typer.Option(None, help="Maximum products to enrich this invocation"),
    retry_failed: bool = typer.Option(False, help="Retry previously failed enrichments"),
):
    """Enrich catalog products with review_count and sold from product pages."""
    db_path = crawl_dir / "catalog.db"
    if not db_path.exists():
        print(f"Catalog database not found: {db_path}")
        raise typer.Exit(code=1)

    store = CatalogStore(db_path, data_dir=crawl_dir)

    spider = CatalogEnrichSpider(
        crawl_run_id=run_id,
        store=store,
        limit=limit,
        retry_failed=retry_failed,
    )

    spider.start()

    stats = store.enrichment_stats(run_id)
    print(f"Enrichment stats for {run_id}: {stats}")


@app.command()
def catalog_export(
    crawl_dir: Path = typer.Option("crawl_state/catalog", help="Directory containing catalog database"),
    run_id: str = typer.Option(..., help="Catalog run ID to export"),
    output_dir: Path = typer.Option("data/processed", help="Directory for exported dataset"),
    require_enrichment: bool = typer.Option(
        False,
        help="Export only PDP-enriched rows (reference-dataset semantics: review_count "
        "and sold always from the product page)",
    ),
):
    """Export merged catalog data to the reference-schema CSV."""
    db_path = crawl_dir / "catalog.db"
    if not db_path.exists():
        print(f"Catalog database not found: {db_path}")
        raise typer.Exit(code=1)

    store = CatalogStore(db_path, data_dir=crawl_dir)

    if store.count_products(run_id) == 0:
        print(f"No products found for run {run_id}")
        raise typer.Exit(code=1)

    unenriched = len(store.pending_enrichment(run_id))
    if unenriched and not require_enrichment:
        print(
            f"Warning: {unenriched} products not yet enriched — their review_count "
            "will be empty and sold falls back to the bucket floor. "
            "Run catalog-enrich first, or use --require-enrichment."
        )

    run_out_dir = output_dir / run_id
    csv_path = run_out_dir / "tokopedia_products_v2.csv"

    store.export_products_csv(csv_path, run_id, require_enrichment=require_enrichment)
    print(f"Exported to {csv_path}")


@app.command()
def quality(
    run_id: str = typer.Option(..., help="Crawl run ID to evaluate"),
    crawl_dir: Path = typer.Option("crawl_state/tokopedia_laptop", help="Directory containing crawl database"),
    report_dir: Path = typer.Option("reports", help="Directory for quality reports"),
):
    """Generate a quality report for a specific crawl run."""
    db_path = crawl_dir / "laptops.db"
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    run_report_dir = report_dir / run_id
    run_report_dir.mkdir(parents=True, exist_ok=True)

    report_data = generate_quality_report(store=store, run_id=run_id)
    json_path = export_quality_report(run_report_dir, report_data)

    md_path = run_report_dir / "quality.md"
    md_content = f"# Quality Report: {run_id}\n\n"
    for k, v in report_data.items():
        md_content += f"- **{k}**: {v}\n"
    md_path.write_text(md_content, encoding="utf-8")

    manifest_data = generate_manifest(
        crawl_run_id=run_id,
        observed_total_data_min=report_data.get("observed_total_data_min"),
        observed_total_data_max=report_data.get("observed_total_data_max"),
    )
    manifest_path = write_manifest(run_report_dir, manifest_data)

    print(f"Quality reports written to {json_path}, {md_path}, and {manifest_path}")



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


@app.command("audit-features")
def audit_features_cmd(
    run_id: str = typer.Option(..., "--run-id", help="Crawl run ID to audit"),
    crawl_dir: Path = typer.Option(
        Path("crawl_state"), "--crawl-dir", help="Directory containing crawl state and database"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Directory to save audit artifacts (default: reports/<run_id>/)"
    ),
    strict: bool = typer.Option(False, "--strict", help="Return non-zero exit code if integrity checks fail"),
) -> None:
    """Execute feature availability and dataset integrity audit on a crawl run."""
    db_candidate_1 = crawl_dir / run_id / "laptops.db"
    db_candidate_2 = crawl_dir / "laptops.db"
    if db_candidate_1.is_file():
        db_path = db_candidate_1
    elif db_candidate_2.is_file():
        db_path = db_candidate_2
    else:
        db_path = db_candidate_1

    store = SQLiteStore(db_path, data_dir=crawl_dir)

    raw_candidates = [
        crawl_dir / run_id,
        crawl_dir / "raw" / run_id,
        Path("data/raw") / run_id,
        crawl_dir,
    ]
    raw_dir = next(
        (d for d in raw_candidates if (d / "products.jsonl").is_file()),
        next((d for d in raw_candidates if d.is_dir()), crawl_dir / run_id),
    )

    if output_dir is None:
        output_dir = Path("reports") / run_id

    report = audit_features(run_id=run_id, store=store, raw_dir=raw_dir)
    json_path, md_path = export_feature_audit(report, output_dir)

    strong_count = sum(
        1 for r in report.results if r.suitability == FeatureSuitability.STRONG_CANDIDATE
    )
    conditional_count = sum(
        1 for r in report.results if r.suitability == FeatureSuitability.CONDITIONAL
    )
    weak_count = sum(
        1 for r in report.results if r.suitability == FeatureSuitability.WEAK_CANDIDATE
    )
    unusable_count = sum(
        1 for r in report.results if r.suitability == FeatureSuitability.UNUSABLE
    )

    typer.echo("Feature Audit Completed\n")
    typer.echo(f"Run: {run_id}")
    typer.echo(f"Eligible Products: {report.total_eligible_listings}\n")
    typer.echo(f"Strong candidates: {strong_count}")
    typer.echo(f"Conditional: {conditional_count}")
    typer.echo(f"Weak: {weak_count}")
    typer.echo(f"Unusable: {unusable_count}\n")
    typer.echo(f"JSON: {json_path}")
    typer.echo(f"Markdown: {md_path}")

    if strict and (
        report.integrity.missing_raw_counterparts > 0
        or report.integrity.orphan_normalized_records > 0
    ):
        raise typer.Exit(code=1)


@app.command("audit-ml-readiness")
def audit_ml_readiness_cmd(
    run_id: str = typer.Option(..., "--run-id", help="Crawl run ID to audit"),
    config_path: Path = typer.Option(
        Path("config/ml_readiness.yaml"), "--config", help="ML readiness config YAML"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Output directory for audit report artifacts"
    ),
    crawl_dir: Path = typer.Option(
        Path("crawl_state"), "--crawl-dir", help="Directory containing crawl state and database"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Return non-zero exit code if dataset integrity checks fail"
    ),
    sample_extremes: int | None = typer.Option(
        None, "--sample-extremes", help="Override max extreme price cases to review"
    ),
) -> None:
    """Execute EDA & ML dataset readiness audit on a crawl run."""
    db_candidates = [
        crawl_dir / run_id / "laptops.db",
        crawl_dir / "laptops.db",
        crawl_dir / run_id / "crawl.sqlite3",
        Path("data/interim") / run_id / "crawl.sqlite3",
    ]
    db_path = next((p for p in db_candidates if p.is_file()), crawl_dir / run_id / "laptops.db")
    store = SQLiteStore(db_path, data_dir=crawl_dir)

    raw_candidates = [
        crawl_dir / run_id,
        crawl_dir / "raw" / run_id,
        Path("data/raw") / run_id,
        crawl_dir,
    ]
    raw_dir = next(
        (d for d in raw_candidates if (d / "products.jsonl").is_file()),
        next((d for d in raw_candidates if d.is_dir()), crawl_dir / run_id),
    )

    if output_dir is None:
        output_dir = Path("reports") / run_id

    config = load_ml_readiness_config(config_path)
    write_kwargs = {}
    if sample_extremes is not None:
        config.extremes.sample_limit = sample_extremes
        write_kwargs["maximum_extreme_cases"] = sample_extremes

    report = run_ml_readiness_audit(
        run_id=run_id,
        store=store,
        raw_jsonl_path=raw_dir,
        config=config,
    )
    _json_path, md_path, _extreme_csv, _missing_csv = write_ml_readiness_artifacts(
        report,
        output_dir=output_dir,
        **write_kwargs,
    )

    typer.echo("ML Dataset Readiness Audit Completed\n")
    typer.echo(f"Run: {run_id}")
    typer.echo(f"Rows: {report.dataset_rows}\n")
    typer.echo("Candidate representations:")
    for rep_id, rep in report.representations.items():
        feats_str = " + ".join(rep.required_features)
        status_str = rep.status.value if hasattr(rep.status, "value") else str(rep.status)
        typer.echo(f"  {rep_id} {feats_str}:")
        typer.echo(f"    Complete: {rep.complete_rows} ({rep.retention_percent:.1f}%)")
        typer.echo(f"    Status: {status_str}")

    typer.echo(f"\nExtreme price observations: {len(report.extreme_prices)}")
    typer.echo(f"Missingness review cases: {len(report.missingness.cases)}\n")
    typer.echo("Report:")
    typer.echo(f"{md_path}")

    if strict and not report.integrity.passed:
        raise typer.Exit(code=1)


@app.command("production-run")
def production_run_cmd(
    production_config: Path = typer.Option(
        Path("config/production.yaml"), "--production-config", help="Production pipeline config YAML"
    ),
    seed_config: Path = typer.Option(
        Path("config/seeds.yaml"), "--seed-config", help="Search seeds config YAML"
    ),
    crawl_dir: Path = typer.Option(
        Path("crawl_state/production"), "--crawl-dir", help="Output directory for crawl state"
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Custom run ID (or auto-generated timestamp)"
    ),
    resume: bool = typer.Option(
        True, "--resume", help="Resume from last completed pipeline stage"
    ),
    skip_audit: bool = typer.Option(
        False, "--skip-audit", help="Skip feature audit stage"
    ),
) -> None:
    """Execute the full end-to-end production dataset pipeline."""
    pipeline = ProductionPipeline(
        production_config_path=production_config,
        seed_config_path=seed_config,
        crawl_dir=crawl_dir,
        run_id=run_id,
        resume=resume,
        skip_audit=skip_audit,
    )
    state = pipeline.run()
    typer.echo(f"Production pipeline run completed: run_id={state.run_id}, stage={state.stage.value}")


@app.command("freeze-ml-dataset")
def freeze_ml_dataset_cmd(
    run_id: str = typer.Option(..., "--run-id", help="Source crawl run ID"),
    config: Path = typer.Option(
        Path("config/ml_freeze.yaml"), "--config", help="ML freeze config YAML"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Base output directory"
    ),
    review_decisions: Path | None = typer.Option(
        None, "--review-decisions", help="Path to manual low-price review decisions CSV"
    ),
    baseline_decisions: Path | None = typer.Option(
        None, "--baseline-decisions", help="Path to immediate predecessor cleaning decisions CSV"
    ),
    baseline_artifact: str = typer.Option(
        "ml-dataset-v1.0.1", "--baseline-artifact", help="Immediate predecessor artifact name"
    ),
    artifact_version: str | None = typer.Option(
        None, "--artifact-version", help="Override artifact release version name"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Fail on validation warnings/errors or unreviewed items"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run preview without finalizing artifacts"
    ),
) -> None:
    """Freeze audited Tokopedia dataset into immutable ML datasets."""
    if strict and (review_decisions is None or not review_decisions.exists()):
        typer.echo("Error: --strict mode requires an existing --review-decisions file.", err=True)
        raise typer.Exit(code=1)

    # Resolve default paths
    db_path = Path(f"data/interim/{run_id}/crawl.sqlite3")
    if not db_path.exists():
        # Fallback to standard crawl_state directory
        db_path = Path(f"crawl_state/{run_id}/laptops.db")
        if not db_path.exists():
            db_path = Path("crawl_state/production/laptops.db")

    raw_jsonl = Path(f"data/raw/{run_id}/products.jsonl")
    if not raw_jsonl.exists():
        raw_jsonl = Path(f"crawl_state/{run_id}/products.jsonl")
        if not raw_jsonl.exists():
            raw_jsonl = Path("crawl_state/production/products.jsonl")

    readiness_json = Path(f"reports/{run_id}/ml_readiness.json")
    extreme_csv = Path(f"reports/{run_id}/extreme_price_review.csv")
    missingness_csv = Path(f"reports/{run_id}/missingness_cases.csv")

    base_output = output_dir if output_dir else Path(f"data/ml/{run_id}")

    store = SQLiteStore(db_path, data_dir=db_path.parent)

    try:
        result = freeze_ml_dataset(
            run_id=run_id,
            config_path=config,
            store=store,
            raw_jsonl_path=raw_jsonl,
            readiness_json_path=readiness_json,
            extreme_review_path=extreme_csv,
            missingness_review_path=missingness_csv,
            output_dir=base_output,
            review_decisions_path=review_decisions,
            baseline_decisions_path=baseline_decisions,
            baseline_artifact=baseline_artifact,
            artifact_version=artifact_version,
            strict=strict,
            dry_run=dry_run,
        )

        typer.echo("ML Dataset Freeze Completed\n")
        typer.echo(f"Source run: {run_id}")
        typer.echo(f"Source rows: {result.source_row_count}\n")
        typer.echo("R1 price + rating:")
        typer.echo(f"  rows: {result.r1_rows}")
        typer.echo("R2 price + rating + review_count:")
        typer.echo(f"  rows: {result.r2_rows}\n")
        typer.echo(f"Manifest: {result.manifest_path}")

    except Exception as e:
        typer.echo(f"Error during freeze: {e}", err=True)
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()



