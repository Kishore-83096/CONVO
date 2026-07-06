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


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    value_num = num(value)
    if value_num is not None:
        return f"{value_num:.2f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")


def metric_avg(row: dict[str, Any] | None, name: str) -> float | None:
    if not row:
        return None
    return num((row.get(name) or {}).get("avg"))


def metric_total(row: dict[str, Any] | None, name: str) -> float | None:
    if not row:
        return None
    return num((row.get(name) or {}).get("total"))


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


def best_throughput(report: dict[str, Any]) -> tuple[Any, float | None]:
    best = None
    for row in (report.get("benchmark") or {}).get("per_level") or []:
        value = num(row.get("successful_messages_per_second", row.get("messages_per_second")))
        if value is None:
            continue
        if best is None or value > best[1]:
            best = (row.get("concurrency"), value)
    return best if best is not None else (None, None)


def container_stats(report: dict[str, Any], contains: str) -> tuple[float | None, float | None]:
    containers = (
        (report.get("request_gap_analysis") or {})
        .get("host_docker_stats", {})
        .get("containers", {})
    )
    contains_lower = contains.lower()
    for name, stats in containers.items():
        if contains_lower not in str(name).lower():
            continue
        cpu = stats.get("cpu_percent") or {}
        return num(cpu.get("avg")), num(cpu.get("p95"))
    return None, None


def config_name(row: dict[str, Any] | None) -> str:
    if not row:
        return "unavailable"
    return str(row.get("config_name") or row.get("run_label") or "run")


def summarize_run(metadata: dict[str, Any]) -> dict[str, Any]:
    messenger_env = metadata.get("messenger_env") or {}
    if not metadata.get("json_report_path"):
        return {
            "config_name": metadata.get("run_label"),
            "messenger_process_role": messenger_env.get("MESSENGER_PROCESS_ROLE", "http"),
            "web_concurrency": messenger_env.get("WEB_CONCURRENCY"),
            "asgi_threads": messenger_env.get("ASGI_THREADS"),
            "gunicorn_backlog": messenger_env.get("GUNICORN_BACKLOG"),
            "cleanup_success": False,
            "json_report_path": "",
            "gap_report_path": "",
        }

    report = load_json(metadata["json_report_path"])
    level_100 = find_gap_level(report, 100)
    best_level, best_mps = best_throughput(report)
    benchmark_summary = report.get("summary") or {}
    status_counts = benchmark_summary.get("status_counts") or {}
    measured_failure_count = int(benchmark_summary.get("failure_count") or 0)
    http_5xx_count = sum(
        int(count)
        for status, count in status_counts.items()
        if str(status).isdigit() and int(status) >= 500
    )
    disqualification_reasons = []
    if not metadata.get("benchmark_succeeded"):
        disqualification_reasons.append("benchmark_failed")
    if measured_failure_count:
        disqualification_reasons.append("measured_failures_present")
    if http_5xx_count:
        disqualification_reasons.append("http_5xx_present")
    if report.get("cleanup_success") is not True:
        disqualification_reasons.append("cleanup_failed")
    if level_100 is None:
        disqualification_reasons.append("missing_c100_result")
    messenger_cpu_avg, messenger_cpu_p95 = container_stats(report, "messenger")
    mysql_cpu_avg, _ = container_stats(report, "mysql")
    redis_cpu_avg, _ = container_stats(report, "redis")
    gap = report.get("request_gap_analysis") or {}

    return {
        "config_name": metadata.get("run_label"),
        "messenger_process_role": messenger_env.get("MESSENGER_PROCESS_ROLE", "http"),
        "web_concurrency": messenger_env.get("WEB_CONCURRENCY"),
        "asgi_threads": messenger_env.get("ASGI_THREADS"),
        "gunicorn_backlog": messenger_env.get("GUNICORN_BACKLOG"),
        "concurrency_100_client_avg_ms": metric_avg(level_100, "client_latency_ms"),
        "concurrency_100_overall_req_total_ms": metric_total(level_100, "overall_client_request_time_ms"),
        "concurrency_100_main_django_total_ms": metric_total(level_100, "main_django_logic_time_ms"),
        "concurrency_100_main_django_avg_ms": metric_avg(level_100, "main_django_logic_time_ms"),
        "concurrency_100_gunicorn_avg_ms": metric_avg(level_100, "gunicorn_request_ms"),
        "concurrency_100_client_or_network_gap_avg_ms": metric_avg(level_100, "client_or_network_gap_ms"),
        "concurrency_100_gunicorn_outside_view_avg_ms": metric_avg(level_100, "gunicorn_outside_view_ms"),
        "concurrency_100_view_total_avg_ms": metric_avg(level_100, "view_total_ms"),
        "concurrency_100_service_total_avg_ms": metric_avg(level_100, "service_total_ms"),
        "concurrency_100_messages_per_second": level_100.get("successful_messages_per_second", level_100.get("messages_per_second")) if level_100 else None,
        "concurrency_100_successful_messages_per_second": level_100.get("successful_messages_per_second", level_100.get("messages_per_second")) if level_100 else None,
        "concurrency_100_offered_requests_per_second": level_100.get("offered_requests_per_second") if level_100 else None,
        "measured_failure_count": measured_failure_count,
        "http_5xx_count": http_5xx_count,
        "eligible_for_recommendation": not disqualification_reasons,
        "disqualification_reasons": disqualification_reasons,
        "best_throughput_level": best_level,
        "best_messages_per_second": best_mps,
        "matched_request_count": gap.get("matched_request_count", metadata.get("matched_request_count")),
        "unmatched_percent": gap.get("unmatched_percent", metadata.get("unmatched_percent")),
        "messenger_cpu_avg": messenger_cpu_avg,
        "messenger_cpu_p95": messenger_cpu_p95,
        "mysql_cpu_avg": mysql_cpu_avg,
        "redis_cpu_avg": redis_cpu_avg,
        "cleanup_success": report.get("cleanup_success", metadata.get("cleanup_success")),
        "json_report_path": metadata.get("json_report_path"),
        "gap_report_path": metadata.get("gap_report_path"),
    }


def best_by(rows: list[dict[str, Any]], key: str, *, highest: bool = False) -> dict[str, Any] | None:
    usable = [row for row in rows if num(row.get(key)) is not None]
    if not usable:
        return None
    return max(usable, key=lambda row: num(row.get(key)) or 0) if highest else min(usable, key=lambda row: num(row.get(key)) or 0)


def recommendation_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        num(row.get("concurrency_100_client_avg_ms")) or 1e12,
        num(row.get("concurrency_100_client_or_network_gap_avg_ms")) or 1e12,
        num(row.get("concurrency_100_gunicorn_outside_view_avg_ms")) or 1e12,
        -(num(row.get("concurrency_100_successful_messages_per_second")) or 0),
    )


def lowest_failure_baseline(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    usable = [row for row in rows if row.get("config_name")]
    if not usable:
        return None
    return min(
        usable,
        key=lambda row: (
            int(row.get("measured_failure_count") or 0),
            int(row.get("http_5xx_count") or 0),
            recommendation_sort_key(row),
        ),
    )


def write_report(rows: list[dict[str, Any]], output_md: Path) -> None:
    headers = [
        "config_name",
        "messenger_process_role",
        "web_concurrency",
        "asgi_threads",
        "gunicorn_backlog",
        "concurrency_100_client_avg_ms",
        "concurrency_100_overall_req_total_ms",
        "concurrency_100_main_django_total_ms",
        "concurrency_100_main_django_avg_ms",
        "concurrency_100_gunicorn_avg_ms",
        "concurrency_100_client_or_network_gap_avg_ms",
        "concurrency_100_gunicorn_outside_view_avg_ms",
        "concurrency_100_view_total_avg_ms",
        "concurrency_100_service_total_avg_ms",
        "concurrency_100_messages_per_second",
        "best_throughput_level",
        "best_messages_per_second",
        "matched_request_count",
        "unmatched_percent",
        "messenger_cpu_avg",
        "messenger_cpu_p95",
        "mysql_cpu_avg",
        "redis_cpu_avg",
        "cleanup_success",
        "eligible_for_recommendation",
        "disqualification_reasons",
        "measured_failure_count",
        "http_5xx_count",
        "json_report_path",
        "gap_report_path",
    ]
    lines = [
        "# Myna ASGI HTTP Tuning Comparison",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(header)) for header in headers) + " |")

    eligible_rows = [row for row in rows if row.get("eligible_for_recommendation")]
    recommended = min(eligible_rows, key=recommendation_sort_key) if eligible_rows else None
    lowest_gap = best_by(eligible_rows, "concurrency_100_client_or_network_gap_avg_ms")
    highest_mps = best_by(eligible_rows, "best_messages_per_second", highest=True)
    lowest_outside = best_by(eligible_rows, "concurrency_100_gunicorn_outside_view_avg_ms")
    diagnostic_baseline = lowest_failure_baseline(rows)

    lines.extend(["", "## Conclusion", ""])
    lines.append(
        "- Best ASGI HTTP config by lowest C100 client_or_network_gap_avg_ms: "
        f"`{config_name(lowest_gap)}` ({fmt(lowest_gap.get('concurrency_100_client_or_network_gap_avg_ms'))} ms)"
        if lowest_gap
        else "- Best ASGI HTTP config by lowest C100 client_or_network_gap_avg_ms: unavailable"
    )
    lines.append(
        "- Best ASGI HTTP config by highest throughput: "
        f"`{config_name(highest_mps)}` ({fmt(highest_mps.get('best_messages_per_second'))} msg/s)"
        if highest_mps
        else "- Best ASGI HTTP config by highest throughput: unavailable"
    )
    lines.append(
        "- Best ASGI HTTP config by lowest gunicorn_outside_view_avg_ms: "
        f"`{config_name(lowest_outside)}` ({fmt(lowest_outside.get('concurrency_100_gunicorn_outside_view_avg_ms'))} ms)"
        if lowest_outside
        else "- Best ASGI HTTP config by lowest gunicorn_outside_view_avg_ms: unavailable"
    )
    if recommended:
        lines.append(
            "- Recommended next runtime setting: "
            f"`{config_name(recommended)}` with MESSENGER_PROCESS_ROLE `http`, "
            f"WEB_CONCURRENCY `{recommended.get('web_concurrency')}`, "
            f"ASGI_THREADS `{recommended.get('asgi_threads')}`, "
            f"GUNICORN_BACKLOG `{recommended.get('gunicorn_backlog')}`."
        )
    else:
        lines.append("- Recommended next runtime setting: `NO VALID MATRIX WINNER`.")
        if diagnostic_baseline:
            lines.append(
                "- LOWEST-FAILURE DIAGNOSTIC BASELINE: "
                f"`{config_name(diagnostic_baseline)}` with failures "
                f"`{diagnostic_baseline.get('measured_failure_count')}` and HTTP 5xx "
                f"`{diagnostic_baseline.get('http_5xx_count')}`."
            )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-manifest", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    manifest = load_json(args.runs_manifest)
    rows = [summarize_run(run) for run in manifest.get("runs", [])]
    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    write_report(rows, output_md)
    print(json.dumps({"output_md": str(output_md), "row_count": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
