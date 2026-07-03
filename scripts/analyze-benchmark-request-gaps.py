#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from pathlib import Path
from typing import Any


GUNICORN_KV_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)="
    r'(?P<value>"[^"]*"|<[^>]*>|[^\s]+)'
)


def unquote_log_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    if len(value) >= 2 and value[0] == "<" and value[-1] == ">":
        return value[1:-1]
    return value


def parse_gunicorn_line(line: str) -> dict[str, str]:
    return {
        match.group("key"): unquote_log_value(match.group("value"))
        for match in GUNICORN_KV_RE.finditer(line)
    }


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp_tiny_negative(value: float) -> tuple[float, bool]:
    if -2.0 <= value < 0:
        return 0.0, False
    return value, value < -2.0


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def summary(values: list[float]) -> dict[str, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"min": None, "max": None, "avg": None, "median": None, "p95": None}
    return {
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "avg": round(sum(clean) / len(clean), 2),
        "median": round(statistics.median(clean), 2),
        "p95": percentile(clean, 0.95),
    }


def load_gunicorn_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = parse_gunicorn_line(line)
        if not fields:
            continue
        request_id = fields.get("req", "").strip()
        if not request_id or request_id == "-":
            continue
        duration_us = fields.get("duration_us", "").strip()
        if not duration_us.isdigit():
            continue
        rows[request_id] = {
            "run_id": fields.get("run", ""),
            "request_id": request_id,
            "phase": fields.get("phase", ""),
            "concurrency": fields.get("concurrency", ""),
            "duration_us": int(duration_us),
            "method": fields.get("method", ""),
            "path": fields.get("path", ""),
            "pid": fields.get("pid", ""),
            "raw": line,
        }
    return rows


def load_host_stats_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "path": str(path)}
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    by_container: dict[str, dict[str, Any]] = {}
    for container in sorted({row.get("container", "") for row in rows if row.get("container")}):
        container_rows = [row for row in rows if row.get("container") == container]
        cpu = [number(row.get("cpu_percent"), None) for row in container_rows]
        mem = [number(row.get("mem_percent"), None) for row in container_rows]
        by_container[container] = {
            "sample_count": len(container_rows),
            "cpu_percent": summary([value for value in cpu if value is not None]),
            "mem_percent": summary([value for value in mem if value is not None]),
        }
    return {
        "available": True,
        "path": str(path),
        "sample_count": len(rows),
        "containers": by_container,
    }


def iter_level_records(report: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for level in report.get("benchmark", {}).get("per_level", []) or []:
        for record in level.get("request_records", []) or []:
            pairs.append((level, record))
    return pairs


def level_identity(level: dict[str, Any]) -> str:
    endpoint = str(level.get("endpoint") or "").strip()
    method = str(level.get("method") or "").strip()
    path = str(level.get("path") or "").strip()
    concurrency = str(level.get("concurrency"))
    return "\x1f".join([endpoint, method, path, concurrency])


def analyze(report: dict[str, Any], gunicorn_rows: dict[str, dict[str, Any]], host_stats: dict[str, Any]) -> dict[str, Any]:
    per_level_records: dict[str, list[dict[str, Any]]] = {}
    unmatched = 0
    matched = 0
    suspicious_negative_count = 0

    for level, record in iter_level_records(report):
        request_id = str(record.get("benchmark_request_id") or "").strip()
        if not request_id:
            unmatched += 1
            continue
        gunicorn = gunicorn_rows.get(request_id)
        if not gunicorn:
            unmatched += 1
            continue

        matched += 1
        server_timing = record.get("server_timing_ms") or {}
        client_latency_ms = number(record.get("latency_ms"))
        gunicorn_request_ms = number(gunicorn.get("duration_us")) / 1000.0
        view_total_ms = number(server_timing.get("view_total"))
        service_total_ms = number(server_timing.get("service_total"))
        realtime_enqueue_ms = number(server_timing.get("view_realtime_outbox_enqueue"))
        view_without_realtime_ms = view_total_ms - realtime_enqueue_ms
        client_or_network_gap_ms, client_suspicious = clamp_tiny_negative(client_latency_ms - gunicorn_request_ms)
        gunicorn_outside_view_ms, gunicorn_suspicious = clamp_tiny_negative(gunicorn_request_ms - view_total_ms)
        if client_suspicious or gunicorn_suspicious:
            suspicious_negative_count += 1

        key = level_identity(level)
        per_level_records.setdefault(key, []).append(
            {
                "request_id": request_id,
                "client_latency_ms": round(client_latency_ms, 2),
                "gunicorn_request_ms": round(gunicorn_request_ms, 2),
                "client_or_network_gap_ms": round(client_or_network_gap_ms, 2),
                "gunicorn_outside_view_ms": round(gunicorn_outside_view_ms, 2),
                "view_total_ms": round(view_total_ms, 2),
                "view_without_realtime_ms": round(view_without_realtime_ms, 2),
                "realtime_enqueue_ms": round(realtime_enqueue_ms, 2),
                "service_total_ms": round(service_total_ms, 2),
            }
        )

    per_level = []
    for level in report.get("benchmark", {}).get("per_level", []) or []:
        key = level_identity(level)
        rows = per_level_records.get(key, [])
        total_requests = level.get("total_messages", level.get("total_requests", 0))
        item: dict[str, Any] = {
            "endpoint": level.get("endpoint"),
            "method": level.get("method"),
            "path": level.get("path"),
            "concurrency": level.get("concurrency"),
            "total_messages": total_requests,
            "total_requests": total_requests,
            "success_count": level.get("success_count"),
            "failure_count": level.get("failure_count"),
            "messages_per_second": level.get("messages_per_second"),
            "requests_per_second": level.get("requests_per_second", level.get("messages_per_second")),
            "matched_request_count": len(rows),
            "unmatched_request_count": max(0, int(total_requests or 0) - len(rows)),
        }
        for metric in (
            "client_latency_ms",
            "gunicorn_request_ms",
            "client_or_network_gap_ms",
            "gunicorn_outside_view_ms",
            "view_total_ms",
            "view_without_realtime_ms",
            "realtime_enqueue_ms",
            "service_total_ms",
        ):
            item[metric] = summary([row[metric] for row in rows])
        per_level.append(item)

    total = matched + unmatched
    unmatched_percent = round((unmatched / total) * 100, 2) if total else 0.0
    return {
        "method": "client_latency_minus_gunicorn_minus_existing_server_timing",
        "matched_request_count": matched,
        "unmatched_request_count": unmatched,
        "unmatched_percent": unmatched_percent,
        "suspicious_negative_gap_count": suspicious_negative_count,
        "gunicorn_access_log_path": None,
        "host_docker_stats": host_stats,
        "per_level": per_level,
    }


def bottleneck_for_level(item: dict[str, Any]) -> str:
    metrics = {
        "client/network": number(item.get("client_or_network_gap_ms", {}).get("avg")),
        "gunicorn/asgi/django outside-view": number(item.get("gunicorn_outside_view_ms", {}).get("avg")),
        "messenger view without realtime": number(item.get("view_without_realtime_ms", {}).get("avg")),
        "realtime enqueue": number(item.get("realtime_enqueue_ms", {}).get("avg")),
        "service/database": number(item.get("service_total_ms", {}).get("avg")),
    }
    return max(metrics, key=metrics.get)


def write_markdown(report: dict[str, Any], markdown_path: Path) -> None:
    analysis = report.get("request_gap_analysis") or {}
    rows = analysis.get("per_level") or []
    has_endpoint_rows = any(row.get("endpoint") for row in rows)
    dominant = "unknown"
    if rows:
        totals: dict[str, float] = {}
        for row in rows:
            name = bottleneck_for_level(row)
            totals[name] = totals.get(name, 0.0) + 1
        dominant = max(totals, key=totals.get)

    lines = [
        "# Myna Request Gap Analysis",
        "",
        "## Executive Summary",
        "",
        f"- Matched requests: `{analysis.get('matched_request_count', 0)}`",
        f"- Unmatched requests: `{analysis.get('unmatched_request_count', 0)}` (`{analysis.get('unmatched_percent', 0)}`%)",
        f"- Most common top bottleneck: `{dominant}`",
        "",
        "## Per-Concurrency Timing",
        "",
    ]
    if has_endpoint_rows:
        lines.extend(
            [
                "| endpoint | method | path | concurrency | requests | success | client_avg_ms | gunicorn_avg_ms | client_or_network_gap_avg_ms | gunicorn_outside_view_avg_ms | view_total_avg_ms | service_total_avg_ms | requests_per_second |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
    else:
        lines.extend(
            [
                "| concurrency | messages | success | client_avg_ms | gunicorn_avg_ms | client_or_network_gap_avg_ms | gunicorn_outside_view_avg_ms | view_total_avg_ms | view_without_realtime_avg_ms | realtime_enqueue_avg_ms | service_total_avg_ms | messages_per_second |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
    for row in rows:
        get_avg = lambda name: row.get(name, {}).get("avg")
        if has_endpoint_rows:
            lines.append(
                "| {endpoint} | {method} | {path} | {concurrency} | {requests} | {success} | {client} | {gunicorn} | {client_gap} | {outside} | {view} | {service} | {rps} |".format(
                    endpoint=row.get("endpoint") or "",
                    method=row.get("method") or "",
                    path=row.get("path") or "",
                    concurrency=row.get("concurrency"),
                    requests=row.get("total_requests"),
                    success=row.get("success_count"),
                    client=get_avg("client_latency_ms"),
                    gunicorn=get_avg("gunicorn_request_ms"),
                    client_gap=get_avg("client_or_network_gap_ms"),
                    outside=get_avg("gunicorn_outside_view_ms"),
                    view=get_avg("view_total_ms"),
                    service=get_avg("service_total_ms"),
                    rps=row.get("requests_per_second"),
                )
            )
        else:
            lines.append(
                "| {concurrency} | {messages} | {success} | {client} | {gunicorn} | {client_gap} | {outside} | {view} | {view_no_rt} | {rt} | {service} | {mps} |".format(
                    concurrency=row.get("concurrency"),
                    messages=row.get("total_messages"),
                    success=row.get("success_count"),
                    client=get_avg("client_latency_ms"),
                    gunicorn=get_avg("gunicorn_request_ms"),
                    client_gap=get_avg("client_or_network_gap_ms"),
                    outside=get_avg("gunicorn_outside_view_ms"),
                    view=get_avg("view_total_ms"),
                    view_no_rt=get_avg("view_without_realtime_ms"),
                    rt=get_avg("realtime_enqueue_ms"),
                    service=get_avg("service_total_ms"),
                    mps=row.get("messages_per_second"),
                )
            )

    lines.extend(["", "## Top Bottleneck Per Level", ""])
    for row in rows:
        label = f"{row.get('endpoint')} concurrency `{row.get('concurrency')}`" if row.get("endpoint") else f"concurrency `{row.get('concurrency')}`"
        lines.append(f"- {label}: `{bottleneck_for_level(row)}`")

    lines.extend(["", "## Docker Stats Summary", ""])
    host_stats = analysis.get("host_docker_stats") or {}
    if host_stats.get("available"):
        for container, stats in (host_stats.get("containers") or {}).items():
            lines.append(
                f"- `{container}`: samples `{stats.get('sample_count')}`, "
                f"cpu avg `{stats.get('cpu_percent', {}).get('avg')}`, "
                f"mem avg `{stats.get('mem_percent', {}).get('avg')}`"
            )
    else:
        lines.append("- Host-side Docker stats CSV was not available.")

    lines.extend(
        [
            "",
            "## Warnings",
            "",
            f"- Unmatched request percent: `{analysis.get('unmatched_percent', 0)}`%",
            f"- Suspicious negative gap count: `{analysis.get('suspicious_negative_gap_count', 0)}`",
            "",
            "## Next Recommended Optimization Target",
            "",
            f"Start with `{dominant}` based on the largest average gap category across levels.",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-report", required=True)
    parser.add_argument("--gunicorn-log", required=True)
    parser.add_argument("--docker-stats-csv", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    json_path = Path(args.json_report)
    output_json = Path(args.output_json) if args.output_json else json_path
    markdown_path = Path(args.output_md) if args.output_md else output_json.with_name(output_json.stem + "_request_gap_analysis.md")
    gunicorn_path = Path(args.gunicorn_log)
    docker_stats_path = Path(args.docker_stats_csv)

    report = json.loads(json_path.read_text(encoding="utf-8-sig"))
    gunicorn_rows = load_gunicorn_rows(gunicorn_path)
    host_stats = load_host_stats_summary(docker_stats_path)
    analysis = analyze(report, gunicorn_rows, host_stats)
    analysis["gunicorn_access_log_path"] = str(gunicorn_path)
    report["request_gap_analysis"] = analysis
    report["host_docker_stats_csv_path"] = str(docker_stats_path)
    report["request_gap_analysis_markdown_path"] = str(markdown_path)
    output_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    write_markdown(report, markdown_path)

    print(json.dumps({
        "json_report": str(output_json),
        "markdown_report": str(markdown_path),
        "gunicorn_access_log": str(gunicorn_path),
        "docker_stats_csv": str(docker_stats_path),
        "matched_request_count": analysis["matched_request_count"],
        "unmatched_request_count": analysis["unmatched_request_count"],
        "unmatched_percent": analysis["unmatched_percent"],
    }, indent=2))
    return 0 if analysis["unmatched_percent"] < 50 else 2


if __name__ == "__main__":
    raise SystemExit(main())
