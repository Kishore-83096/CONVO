#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_avg(row: dict[str, Any] | None, name: str) -> float | None:
    if not row:
        return None
    return num((row.get(name) or {}).get("avg"))


def dominant_outside_view_region(
    pre_view_ms: Any,
    post_view_ms: Any,
    *,
    tolerance_ms: float = 0.5,
) -> str:
    pre = num(pre_view_ms)
    post = num(post_view_ms)
    if pre is None or post is None:
        return "unavailable"
    if abs(pre - post) <= tolerance_ms:
        return "tie / approximately equal"
    return "server pre-view" if pre > post else "server post-view"


def find_gap_level(report: dict[str, Any], concurrency: int) -> dict[str, Any] | None:
    rows = (report.get("request_gap_analysis") or {}).get("per_level") or []
    for row in rows:
        if row.get("endpoint"):
            continue
        try:
            if int(row.get("concurrency")) == concurrency:
                return row
        except (TypeError, ValueError):
            continue
    return None


def best_by(rows: list[dict[str, Any]], key: str, *, highest: bool = False) -> dict[str, Any] | None:
    usable = [row for row in rows if num(row.get(key)) is not None]
    if not usable:
        return None
    return max(usable, key=lambda row: num(row.get(key)) or 0) if highest else min(usable, key=lambda row: num(row.get(key)) or 0)


def summarize_run(metadata: dict[str, Any], concurrency: int) -> dict[str, Any]:
    messenger_env = metadata.get("messenger_env") or {}
    summary: dict[str, Any] = {
        "config_name": metadata.get("run_label"),
        "benchmark_succeeded": metadata.get("benchmark_succeeded"),
        "web_concurrency": messenger_env.get("WEB_CONCURRENCY"),
        "asgi_threads": messenger_env.get("ASGI_THREADS"),
        "gunicorn_backlog": messenger_env.get("GUNICORN_BACKLOG"),
        "json_report_path": metadata.get("json_report_path"),
        "gap_report_path": metadata.get("gap_report_path"),
    }

    json_report_path = metadata.get("json_report_path")
    if not json_report_path or not Path(json_report_path).exists():
        summary["validation_error"] = "missing_json_report"
        return summary

    report = load_json(json_report_path)
    level = find_gap_level(report, concurrency)
    benchmark_summary = report.get("summary") or {}
    status_counts = benchmark_summary.get("status_counts") or {}
    measured_failure_count = int(benchmark_summary.get("failure_count") or 0)
    http_5xx_count = sum(
        int(count)
        for status, count in status_counts.items()
        if str(status).isdigit() and int(status) >= 500
    )
    disqualification_reasons = []
    if metadata.get("benchmark_succeeded") is not True:
        disqualification_reasons.append("benchmark_failed")
    if measured_failure_count:
        disqualification_reasons.append("measured_failures_present")
    if http_5xx_count:
        disqualification_reasons.append("http_5xx_present")
    if report.get("cleanup_success") is not True:
        disqualification_reasons.append("cleanup_failed")
    if level is None:
        disqualification_reasons.append(f"missing_concurrency_{concurrency}_gap_row")
    summary.update(
        {
            "client_avg_ms": metric_avg(level, "client_latency_ms"),
            "gunicorn_avg_ms": metric_avg(level, "gunicorn_request_ms"),
            "client_or_network_gap_avg_ms": metric_avg(level, "client_or_network_gap_ms"),
            "gunicorn_outside_view_avg_ms": metric_avg(level, "gunicorn_outside_view_ms"),
            "server_outside_view_avg_ms": metric_avg(level, "server_outside_view_ms"),
            "server_pre_view_avg_ms": metric_avg(level, "server_pre_view_ms"),
            "server_post_view_avg_ms": metric_avg(level, "server_post_view_ms"),
            "dominant_outside_view_region": (
                level.get("dominant_outside_view_region")
                if level
                else "unavailable"
            ) or dominant_outside_view_region(
                metric_avg(level, "server_pre_view_ms"),
                metric_avg(level, "server_post_view_ms"),
            ),
            "messages_per_second": level.get("successful_messages_per_second", level.get("messages_per_second")) if level else None,
            "offered_requests_per_second": level.get("offered_requests_per_second") if level else None,
            "measured_failure_count": measured_failure_count,
            "http_5xx_count": http_5xx_count,
            "eligible_for_recommendation": not disqualification_reasons,
            "disqualification_reasons": disqualification_reasons,
            "matched_request_count": (report.get("request_gap_analysis") or {}).get("matched_request_count"),
            "unmatched_percent": (report.get("request_gap_analysis") or {}).get("unmatched_percent"),
            "cleanup_success": report.get("cleanup_success"),
        }
    )
    if level is None:
        summary["validation_error"] = f"missing_concurrency_{concurrency}_gap_row"
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-manifest", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--expected-run-count", type=int)
    parser.add_argument("--best-concurrency", type=int, default=100)
    args = parser.parse_args()

    manifest_path = Path(args.runs_manifest)
    report_md_path = Path(args.report_md)
    output_json_path = Path(args.output_json)

    manifest = load_json(manifest_path)
    runs = manifest.get("runs") or []
    rows = [summarize_run(run, args.best_concurrency) for run in runs]

    eligible_rows = [row for row in rows if row.get("eligible_for_recommendation")]
    best_gap = best_by(eligible_rows, "client_or_network_gap_avg_ms")
    best_throughput = best_by(eligible_rows, "messages_per_second", highest=True)
    best_outside = best_by(eligible_rows, "gunicorn_outside_view_avg_ms")
    recommended = best_gap or best_outside or best_throughput

    errors: list[str] = []
    warnings: list[str] = []
    if args.expected_run_count is not None and len(runs) != args.expected_run_count:
        errors.append(f"expected {args.expected_run_count} run metadata rows, found {len(runs)}")
    if not recommended:
        warnings.append(f"NO VALID MATRIX WINNER for concurrency {args.best_concurrency}")

    markdown = report_md_path.read_text(encoding="utf-8-sig") if report_md_path.exists() else ""
    if not markdown:
        errors.append(f"missing markdown report: {report_md_path}")
    elif recommended and str(recommended.get("config_name")) not in markdown:
        errors.append("markdown report does not contain recomputed recommended config name")

    missing_reports = [row for row in rows if row.get("validation_error") == "missing_json_report"]
    missing_level_rows = [row for row in rows if row.get("validation_error") and row.get("validation_error") != "missing_json_report"]
    failed_runs = [row for row in rows if row.get("benchmark_succeeded") is False]
    if missing_reports:
        errors.append(f"{len(missing_reports)} run(s) are missing JSON reports")
    if missing_level_rows:
        warnings.append(f"{len(missing_level_rows)} run(s) do not have a comparable concurrency {args.best_concurrency} row")
    if failed_runs:
        warnings.append(f"{len(failed_runs)} run(s) reported benchmark_succeeded=false")

    result = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "run_count": len(runs),
        "expected_run_count": args.expected_run_count,
        "best_concurrency": args.best_concurrency,
        "best_by_lowest_client_or_network_gap": best_gap,
        "best_by_highest_throughput": best_throughput,
        "best_by_lowest_gunicorn_outside_view": best_outside,
        "recommended": recommended,
        "rows": rows,
    }
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("valid", "errors", "warnings", "recommended")}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
