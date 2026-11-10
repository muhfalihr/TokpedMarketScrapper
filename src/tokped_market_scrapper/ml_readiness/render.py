import csv
import json
from pathlib import Path
from typing import Any

from laptop_market_scraper.ml_readiness.models import (
    MLReadinessReport,
    RepresentationStatus,
)


def compute_freeze_recommendation(report: MLReadinessReport) -> tuple[str, str]:
    if not report.integrity.passed:
        return (
            "NOT_READY",
            "Dataset integrity checks failed. Required columns, price formats, or record counts contain unresolved anomalies.",
        )

    rep_statuses = [rep.status for rep in report.representations.values()]
    if any(s == RepresentationStatus.NOT_READY for s in rep_statuses):
        return (
            "NOT_READY",
            "One or more feature candidate representations were evaluated as NOT_READY due to insufficient complete cases or feature availability.",
        )

    if any(s == RepresentationStatus.REVIEW_REQUIRED for s in rep_statuses):
        return (
            "REVIEW_REQUIRED",
            "Candidate representations require manual review of data completeness or feature distributions before dataset freeze.",
        )

    if len(report.extreme_prices) > 0 or any(s == RepresentationStatus.READY_WITH_CAVEATS for s in rep_statuses):
        return (
            "REVIEW_REQUIRED",
            "Dataset contains extreme price observations or candidate representations with caveats requiring human verification prior to freezing.",
        )

    return (
        "READY_FOR_HUMAN_FREEZE_REVIEW",
        "All integrity checks passed, candidate representations meet retention thresholds, and no unresolved blocking anomalies were detected.",
    )


def _fmt(val: Any, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def render_ml_readiness_markdown(report: MLReadinessReport) -> str:
    rec_status, rec_rationale = compute_freeze_recommendation(report)

    lines: list[str] = [
        "# ML Dataset Readiness Audit",
        "",
        "## 1. Dataset Identity",
        f"- **Run ID**: `{report.run_id}`",
        f"- **Generated At**: `{report.generated_at}`",
        f"- **Total Dataset Rows**: `{report.dataset_rows}`",
        f"- **Git Commit**: `{report.provenance.git_commit}`",
        f"- **Acquisition Tag**: `{report.provenance.acquisition_tag}`",
        f"- **Search Contract SHA256**: `{report.provenance.search_contract_sha256}`",
        f"- **Feature Audit SHA256**: `{report.provenance.feature_audit_sha256}`",
        f"- **Readiness Config SHA256**: `{report.provenance.readiness_config_sha256}`",
        "",
        "## 2. Integrity Check",
        f"- **Status**: `{'PASSED' if report.integrity.passed else 'FAILED'}`",
        f"- **Normalized Rows**: `{report.integrity.normalized_rows}`",
        f"- **Raw Rows**: `{report.integrity.raw_rows}`",
        f"- **Unique Normalized Keys**: `{report.integrity.unique_normalized_keys}`",
        f"- **Unique Raw Keys**: `{report.integrity.unique_raw_keys}`",
        f"- **Duplicate Keys**: `{len(report.integrity.duplicate_normalized_keys)}`",
        f"- **Orphan Normalized Records**: `{report.integrity.orphan_normalized_records}`",
        f"- **Orphan Raw Records**: `{report.integrity.orphan_raw_records}`",
        f"- **Missing Required Columns**: `{list(report.integrity.missing_required_columns)}`",
        f"- **Invalid Price Keys Count**: `{len(report.integrity.invalid_price_keys)}`",
        f"- **Invalid Rating Keys Count**: `{len(report.integrity.invalid_rating_keys)}`",
        f"- **Invalid Review Count Keys Count**: `{len(report.integrity.invalid_review_count_keys)}`",
        "",
        "## 3. Candidate Features",
        "The following feature set was audited for ML model readiness:",
        "",
        "| Feature Name | Non-Null Count | Missing Count | Coverage % | Skewness | Transformation Signal |",
        "|--------------|----------------|---------------|------------|----------|-----------------------|",
    ]

    for feat_name, dist in report.distributions.items():
        lines.append(
            f"| `{feat_name}` | {dist.non_null_count} | {dist.missing_count} | {dist.coverage_percent:.1f}% | {_fmt(dist.raw_skewness, 2)} | `{dist.transformation_signal.value}` |"
        )

    lines.extend([
        "",
        "## 4. Missingness Analysis",
        f"- **Total Rows**: `{report.missingness.total_rows}`",
        f"- **Complete Rating & Review Count**: `{report.missingness.complete_rating_and_reviews}`",
        f"- **Missing Rating Only**: `{report.missingness.missing_rating_only}`",
        f"- **Missing Reviews Only**: `{report.missingness.missing_reviews_only}`",
        f"- **Missing Both Rating & Reviews**: `{report.missingness.missing_both}`",
        "",
        "### 4.1 Rating",
        f"- **Missing Rate**: `{report.missingness.rating_missing_percent:.2f}%`",
        "",
        "### 4.2 Review Count",
        f"- **Missing Rate**: `{report.missingness.review_missing_percent:.2f}%`",
        "",
        "### 4.3 Joint Missingness Patterns",
        f"- **Median Price (Review Present)**: `{_fmt(report.missingness.median_price_when_review_present, 2)}`",
        f"- **Median Price (Review Missing)**: `{_fmt(report.missingness.median_price_when_review_missing, 2)}`",
        "",
        "## 5. Complete-Case Analysis",
        "| Representation ID | Required Features | Total Rows | Complete Rows | Dropped Rows | Retention % |",
        "|-------------------|-------------------|------------|---------------|--------------|-------------|",
    ])

    for rep_id, cc in report.complete_cases.items():
        feats = ", ".join(cc.required_features)
        lines.append(
            f"| `{rep_id}` | `{feats}` | {cc.total_rows} | {cc.complete_rows} | {cc.dropped_rows} | {cc.retention_percent:.1f}% |"
        )

    lines.extend([
        "",
        "## 6. Distribution Analysis",
    ])

    for sub_num, feat_key in [("6.1", "price"), ("6.2", "rating"), ("6.3", "review_count")]:
        lines.append(f"### {sub_num} {feat_key.capitalize() if feat_key != 'review_count' else 'Review Count'}")
        if feat_key in report.distributions:
            d = report.distributions[feat_key]
            lines.extend([
                f"- **Non-Null / Total**: `{d.non_null_count}` / `{report.dataset_rows}` (`{d.coverage_percent:.1f}%`)",
                f"- **Min / Q25 / Median / Q75 / Max**: `{_fmt(d.min_value)}` / `{_fmt(d.q25)}` / `{_fmt(d.median)}` / `{_fmt(d.q75)}` / `{_fmt(d.max_value)}`",
                f"- **IQR**: `{_fmt(d.iqr)}`",
                f"- **Raw Skewness**: `{_fmt(d.raw_skewness, 2)}`",
                f"- **Log1p Skewness**: `{_fmt(d.log1p_skewness, 2)}`",
                f"- **Skewness Reduction**: `{_fmt(d.absolute_skew_reduction, 2)}`",
                f"- **Transformation Signal**: `{d.transformation_signal.value}`",
            ])
        else:
            lines.append("- *No distribution data available.*")
        lines.append("")

    lines.extend([
        "## 7. Extreme Price Analysis",
        f"- **Detected Outlier Cases**: `{len(report.extreme_prices)}`",
    ])

    if report.extreme_prices:
        lines.extend([
            "",
            "| Listing Key | Product Name | Price | Robust Z-Score | Triggers | Review Status |",
            "|-------------|--------------|-------|----------------|----------|---------------|",
        ])
        for ep in report.extreme_prices[:10]:
            pname = ep.product_name[:30] + "..." if ep.product_name and len(ep.product_name) > 33 else (ep.product_name or "N/A")
            trig = ";".join(ep.trigger_names)
            lines.append(
                f"| `{ep.listing_key}` | {pname} | `{ep.price:,.0f}` | `{_fmt(ep.robust_z_score, 2)}` | `{trig}` | `{ep.review_status}` |"
            )
        if len(report.extreme_prices) > 10:
            lines.append(f"\n*Showing top 10 of {len(report.extreme_prices)} extreme price cases. Full list in extreme_price_review.csv.*")

    lines.extend([
        "",
        "## 8. Skewness and Transformation Diagnostics",
        "| Feature | Raw Skewness | Log1p Skewness | Skew Reduction | Recommended Transformation |",
        "|---------|--------------|----------------|----------------|----------------------------|",
    ])

    for feat_name, dist in report.distributions.items():
        lines.append(
            f"| `{feat_name}` | {_fmt(dist.raw_skewness, 2)} | {_fmt(dist.log1p_skewness, 2)} | {_fmt(dist.absolute_skew_reduction, 2)} | `{dist.transformation_signal.value}` |"
        )

    lines.extend([
        "",
        "## 9. Variance Analysis",
        "| Feature | Zero Count | Zero Rate % | Unique Values | Dominant Value Rate % | Zero Var Flag | Near-Zero Var Flag |",
        "|---------|------------|-------------|---------------|-----------------------|---------------|--------------------|",
    ])

    for feat_name, dist in report.distributions.items():
        lines.append(
            f"| `{feat_name}` | {dist.zero_count} | {dist.zero_rate:.1f}% | {dist.unique_value_count} | {dist.dominant_value_rate:.1f}% | `{dist.zero_variance_flag}` | `{dist.near_zero_variance_flag}` |"
        )

    lines.extend([
        "",
        "## 10. Correlation and Redundancy",
        "| Feature A | Feature B | Pairwise N | Spearman Rho | Pearson R | Strength | Redundancy Review |",
        "|-----------|-----------|------------|--------------|-----------|----------|-------------------|",
    ])

    for assoc in report.associations:
        lines.append(
            f"| `{assoc.feature_a}` | `{assoc.feature_b}` | {assoc.pairwise_n} | {_fmt(assoc.spearman_rho, 3)} | {_fmt(assoc.pearson_r, 3)} | `{assoc.strength or 'N/A'}` | `{assoc.redundancy_review}` |"
        )

    lines.extend([
        "",
        "## 11. Candidate Representation Readiness",
    ])

    for rep_key, rep_name in [("R1", "R1 — Price + Rating"), ("R2", "R2 — Price + Rating + Review Count")]:
        lines.append(f"### {rep_name}")
        if rep_key in report.representations:
            rep = report.representations[rep_key]
            caveats_str = "; ".join(rep.caveats) if rep.caveats else "None"
            lines.extend([
                f"- **Status**: `{rep.status.value}`",
                f"- **Required Features**: `{', '.join(rep.required_features)}`",
                f"- **Complete Rows**: `{rep.complete_rows}`",
                f"- **Retention Percentage**: `{rep.retention_percent:.1f}%`",
                f"- **Caveats**: {caveats_str}",
            ])
        else:
            lines.append("- *Representation not evaluated in this audit run.*")
        lines.append("")

    lines.extend([
        "## 12. Unresolved Issues",
    ])

    issues: list[str] = []
    if not report.integrity.passed:
        issues.append("Dataset integrity verification failed.")
    if report.integrity.invalid_price_keys:
        issues.append(f"{len(report.integrity.invalid_price_keys)} listing keys have invalid price formatting.")
    if report.extreme_prices:
        issues.append(f"{len(report.extreme_prices)} extreme price observations flagged for human review.")
    
    unresolved_missing = [c for c in report.missingness.cases if c.semantic_status.value == "UNRESOLVED"]
    if unresolved_missing:
        issues.append(f"{len(unresolved_missing)} missingness cases labeled UNRESOLVED.")

    for feat, dist in report.distributions.items():
        if dist.zero_variance_flag:
            issues.append(f"Feature `{feat}` exhibits zero variance.")
        if dist.near_zero_variance_flag:
            issues.append(f"Feature `{feat}` exhibits near-zero variance.")

    for assoc in report.associations:
        if assoc.redundancy_review:
            issues.append(f"High Spearman correlation between `{assoc.feature_a}` and `{assoc.feature_b}` (rho={_fmt(assoc.spearman_rho, 3)}).")

    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("No unresolved integrity issues detected.")

    lines.extend([
        "",
        "## 13. ML Dataset Freeze Recommendation",
        f"- **Recommendation**: `{rec_status}`",
        f"- **Rationale**: {rec_rationale}",
        "",
    ])

    return "\n".join(lines)


def write_ml_readiness_artifacts(
    report: MLReadinessReport,
    *,
    output_dir: Path | str,
    maximum_extreme_cases: int = 20,
    maximum_missingness_cases: int = 30,
) -> tuple[Path, Path, Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "ml_readiness.json"
    md_path = out / "ml_readiness_report.md"
    extreme_csv_path = out / "extreme_price_review.csv"
    missing_csv_path = out / "missingness_cases.csv"

    # 1. JSON
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(report.model_dump(mode="json"), indent=2))

    # 2. Scientific Markdown
    md_text = render_ml_readiness_markdown(report)
    md_path.write_text(md_text, encoding="utf-8")

    # 3. extreme_price_review.csv
    extreme_headers = [
        "listing_key",
        "product_name",
        "product_url",
        "price",
        "breadcrumb",
        "shop_name",
        "trigger_names",
        "robust_z_score",
        "raw_price_value",
        "price_source",
        "review_status",
        "review_note",
    ]
    with open(extreme_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(extreme_headers)
        for obs in report.extreme_prices[:maximum_extreme_cases]:
            writer.writerow([
                obs.listing_key,
                obs.product_name or "",
                obs.product_url or "",
                obs.price,
                obs.breadcrumb or "",
                obs.shop_name or "",
                ";".join(obs.trigger_names),
                obs.robust_z_score if obs.robust_z_score is not None else "",
                obs.raw_price_value if obs.raw_price_value is not None else "",
                obs.price_source or "",
                obs.review_status,
                obs.review_note,
            ])

    # 4. missingness_cases.csv
    missing_headers = [
        "listing_key",
        "product_name",
        "product_url",
        "rating",
        "review_count",
        "rating_missing",
        "review_count_missing",
        "semantic_status",
        "evidence",
        "review_note",
    ]
    with open(missing_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(missing_headers)
        for case in report.missingness.cases[:maximum_missingness_cases]:
            writer.writerow([
                case.listing_key,
                case.product_name or "",
                case.product_url or "",
                case.rating if case.rating is not None else "",
                case.review_count if case.review_count is not None else "",
                case.rating_missing,
                case.review_count_missing,
                case.semantic_status.value if hasattr(case.semantic_status, "value") else str(case.semantic_status),
                ";".join(case.evidence),
                getattr(case, "review_note", ""),
            ])

    return (json_path, md_path, extreme_csv_path, missing_csv_path)
