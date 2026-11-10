"""Rendering module for scientific feature availability audit artifacts (JSON and Markdown)."""

from enum import Enum
from pathlib import Path

from laptop_market_scraper.audit.models import (
    FeatureAuditReport,
    FeatureSuitability,
)


def render_feature_audit_json(
    report: FeatureAuditReport, output_path: Path | str
) -> Path:
    """Render and save structured feature_audit.json matching FeatureAuditReport.model_dump()."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def _format_num(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:.2f}"


def render_feature_audit_markdown(
    report: FeatureAuditReport, output_path: Path | str
) -> Path:
    """Render publication-ready Markdown feature audit report."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    # Title & Metadata
    lines.append("# Feature Availability Audit")
    lines.append("")

    # 1. Audit Metadata
    lines.append("## Audit Metadata")
    lines.append(f"- **Run ID**: `{report.run_id}`")
    lines.append(f"- **Generated At**: `{report.generated_at}`")
    lines.append(f"- **Total Eligible Listings**: `{report.total_eligible_listings}`")
    lines.append("")

    # 2. Dataset Integrity
    lines.append("## Dataset Integrity")
    lines.append(f"- **SQLite Product Count**: {report.integrity.sqlite_product_count}")
    lines.append(f"- **SQLite Discovery Count**: {report.integrity.sqlite_discovery_count}")
    lines.append(f"- **Provenance Record Count**: {report.integrity.provenance_record_count}")
    lines.append(f"- **Raw JSONL Count**: {report.integrity.raw_jsonl_count}")
    lines.append(f"- **Missing Raw Counterparts**: {report.integrity.missing_raw_counterparts}")
    lines.append(f"- **Orphan Raw Records**: {report.integrity.orphan_raw_records}")
    lines.append(f"- **Orphan Normalized Records**: {report.integrity.orphan_normalized_records}")
    lines.append("")

    # Categorize suitability
    strong = [
        r.feature_name
        for r in report.results
        if r.suitability == FeatureSuitability.STRONG_CANDIDATE
    ]
    conditional = [
        r.feature_name
        for r in report.results
        if r.suitability == FeatureSuitability.CONDITIONAL
    ]
    weak = [
        r.feature_name
        for r in report.results
        if r.suitability == FeatureSuitability.WEAK_CANDIDATE
    ]
    unusable = [
        r.feature_name
        for r in report.results
        if r.suitability == FeatureSuitability.UNUSABLE
    ]

    # 3. Feature Availability Summary
    lines.append("## Feature Availability Summary")
    lines.append(f"- **Total Candidate Features Audited**: {len(report.results)}")
    lines.append(f"- **Strong Candidates**: {len(strong)}")
    lines.append(f"- **Conditional Candidates**: {len(conditional)}")
    lines.append(f"- **Weak Candidates**: {len(weak)}")
    lines.append(f"- **Unusable Features**: {len(unusable)}")
    lines.append("")

    # Primary Summary Table
    lines.append("## Primary Summary Table")
    lines.append("")
    lines.append(
        "| Feature | Dimension | Coverage | Missing | Type | Main Source | Median | Min–Max | Reliability | Suitability |"
    )
    lines.append(
        "|---|---|---:|---:|---|---|---:|---|---|---|"
    )

    for res in report.results:
        cov_str = f"{res.coverage_percent:.1f}%"
        miss_str = f"{res.missingness_percent:.1f}%"
        main_source = (
            max(res.source_layers, key=res.source_layers.get)
            if res.source_layers
            else "N/A"
        )
        med_str = _format_num(res.median)
        if res.minimum is not None and res.maximum is not None:
            min_max_str = f"{_format_num(res.minimum)} – {_format_num(res.maximum)}"
        else:
            min_max_str = "N/A"

        rel_str = res.reliability.value if isinstance(res.reliability, Enum) else str(res.reliability)
        suit_str = res.suitability.value if isinstance(res.suitability, Enum) else str(res.suitability)

        lines.append(
            f"| {res.feature_name} | {res.research_dimension} | {cov_str} | {miss_str} | "
            f"{res.observed_dtype} | {main_source} | {med_str} | {min_max_str} | {rel_str} | {suit_str} |"
        )

    lines.append("")

    # Dimension Sub-tables
    dimensions = ["Pricing", "Demand", "Engagement", "Perception"]
    for dim in dimensions:
        dim_results = [r for r in report.results if r.research_dimension == dim]
        lines.append(f"## {dim} Features")
        if not dim_results:
            lines.append("No features recorded for this dimension.")
        else:
            lines.append("| Feature | Coverage | Type | Main Source | Reliability | Suitability |")
            lines.append("|---|---:|---|---|---|---|")
            for res in dim_results:
                cov_str = f"{res.coverage_percent:.1f}%"
                main_source = (
                    max(res.source_layers, key=res.source_layers.get)
                    if res.source_layers
                    else "N/A"
                )
                rel_str = res.reliability.value if isinstance(res.reliability, Enum) else str(res.reliability)
                suit_str = res.suitability.value if isinstance(res.suitability, Enum) else str(res.suitability)
                lines.append(
                    f"| {res.feature_name} | {cov_str} | {res.observed_dtype} | {main_source} | {rel_str} | {suit_str} |"
                )
        lines.append("")

    # 8. Source Provenance
    lines.append("## Source Provenance")
    for res in report.results:
        layers_desc = (
            ", ".join(f"{k}:{v}" for k, v in res.source_layers.items())
            if res.source_layers
            else "None"
        )
        fields_desc = (
            ", ".join(f"{k}:{v}" for k, v in res.source_fields.items())
            if res.source_fields
            else "None"
        )
        lines.append(f"- **{res.feature_name}**: Layers ({layers_desc}) | Fields ({fields_desc})")
    lines.append("")

    # 9. Reliability Notes
    lines.append("## Reliability Notes")
    for res in report.results:
        rel_str = res.reliability.value if isinstance(res.reliability, Enum) else str(res.reliability)
        lines.append(f"- **{res.feature_name}** (`{rel_str}`): {res.semantic_note}")
    lines.append("")

    # 10. Research Recommendation Summary
    lines.append("## Research Recommendation Summary")
    lines.append(f"- **Strong Candidates**: {', '.join(strong) if strong else 'None'}")
    lines.append(f"- **Conditional Candidates**: {', '.join(conditional) if conditional else 'None'}")
    lines.append(f"- **Weak Candidates**: {', '.join(weak) if weak else 'None'}")
    lines.append(f"- **Unusable Features**: {', '.join(unusable) if unusable else 'None'}")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_feature_audit(
    report: FeatureAuditReport, output_dir: Path | str
) -> tuple[Path, Path]:
    """Export both feature_audit.json and feature_audit.md to output_dir."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = render_feature_audit_json(report, out_dir / "feature_audit.json")
    md_path = render_feature_audit_markdown(report, out_dir / "feature_audit.md")
    return json_path, md_path
