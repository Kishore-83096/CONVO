#!/usr/bin/env python3
"""Attach Gunicorn gthread queue/worker distribution analysis to a benchmark JSON report."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-report", required=True, type=Path)
    parser.add_argument("--queue-log", required=True, type=Path)
    return parser.parse_args()


def parse_line(raw_line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in raw_line.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * weight)


def rounded(value: float | None) -> float | None:
    return round(float(value), 2) if value is not None else None


def summarize(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values]
    if not clean:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "avg": None,
            "p50": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
        }
    p50 = percentile(clean, 0.50)
    return {
        "count": len(clean),
        "min": rounded(min(clean)),
        "max": rounded(max(clean)),
        "avg": rounded(statistics.mean(clean)),
        "p50": rounded(p50),
        "median": rounded(p50),
        "p75": rounded(percentile(clean, 0.75)),
        "p90": rounded(percentile(clean, 0.90)),
        "p95": rounded(percentile(clean, 0.95)),
        "p99": rounded(percentile(clean, 0.99)),
    }


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    numerator = sum(left * right for left, right in zip(dx, dy))
    denominator = math.sqrt(
        sum(value * value for value in dx)
        * sum(value * value for value in dy)
    )
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def main() -> int:
    args = parse_args()
    with args.json_report.open("r", encoding="utf-8-sig") as handle:
        report = json.load(handle)
    run_id = str(report.get("run_id") or "").strip()
    levels = list((report.get("benchmark") or {}).get("per_level") or [])

    raw_lines: list[str] = []
    read_error: str | None = None
    try:
        raw_lines = args.queue_log.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        read_error = f"{exc.__class__.__name__}: {exc}"

    parsed_rows = [parse_line(line) for line in raw_lines if line.strip()]
    run_rows = [row for row in parsed_rows if row.get("run") == run_id]
    analysis: dict[str, Any] = {
        "available": False,
        "collector": "messenger_config.benchmark_gthread_worker.BenchmarkThreadWorker",
        "collector_io_mode": "per_worker_simplequeue_background_batch_writer",
        "run_id": run_id,
        "queue_log_present": args.queue_log.is_file(),
        "queue_log_nonempty": bool(raw_lines),
        "queue_log_read_error": read_error,
        "raw_log_line_count": len(raw_lines),
        "matching_run_line_count": len(run_rows),
        "per_level": [],
        "warnings": [],
    }
    if not run_id:
        analysis["warnings"].append(
            "Primary JSON report has no run_id; queue records cannot be correlated."
        )

    for level in levels:
        try:
            concurrency = int(level.get("concurrency"))
        except (TypeError, ValueError):
            continue
        expected_phase = f"send_concurrency_{concurrency}"
        level_rows: list[dict[str, Any]] = []
        for row in run_rows:
            try:
                row_concurrency = int(row.get("concurrency") or 0)
                queue_wait_ms = int(row.get("queue_wait_us") or 0) / 1000.0
            except (TypeError, ValueError):
                continue
            if row_concurrency != concurrency or row.get("phase") != expected_phase:
                continue
            enriched: dict[str, Any] = dict(row)
            enriched["queue_wait_ms"] = queue_wait_ms
            level_rows.append(enriched)

        by_worker: dict[str, list[float]] = defaultdict(list)
        by_thread: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        queue_by_request: dict[str, float] = {}
        for row in level_rows:
            worker_pid = str(row.get("worker_pid") or "missing")
            thread_ident = str(row.get("thread_ident") or "missing")
            thread_name = str(row.get("thread_name") or "missing")
            queue_wait_ms = float(row["queue_wait_ms"])
            by_worker[worker_pid].append(queue_wait_ms)
            by_thread[(worker_pid, thread_ident, thread_name)].append(queue_wait_ms)
            request_id = str(row.get("req") or "").strip()
            if request_id:
                queue_by_request[request_id] = queue_wait_ms

        worker_distribution = [
            {
                "worker_pid": worker_pid,
                "request_count": len(values),
                "request_share_pct": round((len(values) / len(level_rows)) * 100, 2)
                if level_rows else None,
                "queue_wait_ms": summarize(values),
            }
            for worker_pid, values in sorted(
                by_worker.items(), key=lambda item: (-len(item[1]), item[0])
            )
        ]
        thread_distribution = [
            {
                "worker_pid": worker_pid,
                "thread_ident": thread_ident,
                "thread_name": thread_name,
                "request_count": len(values),
                "request_share_pct": round((len(values) / len(level_rows)) * 100, 2)
                if level_rows else None,
                "queue_wait_ms": summarize(values),
            }
            for (worker_pid, thread_ident, thread_name), values in sorted(
                by_thread.items(),
                key=lambda item: (item[0][0], -len(item[1]), item[0][1]),
            )
        ]

        worker_counts = [len(values) for values in by_worker.values()]
        thread_counts = [len(values) for values in by_thread.values()]
        distribution_summary = {
            "worker_count": len(worker_counts),
            "thread_count": len(thread_counts),
            "worker_requests_min": min(worker_counts) if worker_counts else None,
            "worker_requests_max": max(worker_counts) if worker_counts else None,
            "worker_request_spread": max(worker_counts) - min(worker_counts)
            if worker_counts else None,
            "worker_requests_mean": round(statistics.mean(worker_counts), 2)
            if worker_counts else None,
            "worker_requests_stdev": round(statistics.pstdev(worker_counts), 2)
            if worker_counts else None,
            "worker_request_cv_pct": round(
                statistics.pstdev(worker_counts) / statistics.mean(worker_counts) * 100,
                2,
            ) if worker_counts and statistics.mean(worker_counts) != 0 else None,
            "worker_max_to_min_request_ratio": round(
                max(worker_counts) / min(worker_counts), 4
            ) if worker_counts and min(worker_counts) > 0 else None,
            "thread_requests_min": min(thread_counts) if thread_counts else None,
            "thread_requests_max": max(thread_counts) if thread_counts else None,
            "thread_request_spread": max(thread_counts) - min(thread_counts)
            if thread_counts else None,
            "thread_requests_mean": round(statistics.mean(thread_counts), 2)
            if thread_counts else None,
        }

        httpx_wait_by_request: dict[str, float] = {}
        for record in list(level.get("request_records") or []):
            request_id = str(record.get("benchmark_request_id") or "").strip()
            wait_ms = (record.get("httpx_trace_ms") or {}).get("wait_response_headers")
            if request_id and wait_ms is not None:
                try:
                    httpx_wait_by_request[request_id] = float(wait_ms)
                except (TypeError, ValueError):
                    pass

        matched_ids = sorted(set(queue_by_request) & set(httpx_wait_by_request))
        queue_values = [queue_by_request[item] for item in matched_ids]
        httpx_wait_values = [httpx_wait_by_request[item] for item in matched_ids]
        header_wait_minus_queue = [
            httpx_wait_by_request[item] - queue_by_request[item]
            for item in matched_ids
        ]
        queue_summary = summarize([float(row["queue_wait_ms"]) for row in level_rows])
        httpx_wait_summary = (
            (level.get("httpx_trace_ms") or {}).get("wait_response_headers") or {}
        )
        queue_avg = queue_summary.get("avg")
        httpx_wait_avg = httpx_wait_summary.get("avg")
        request_correlation = {
            "matched_request_count": len(matched_ids),
            "queue_request_count": len(queue_by_request),
            "httpx_wait_request_count": len(httpx_wait_by_request),
            "unmatched_queue_request_count": len(set(queue_by_request) - set(httpx_wait_by_request)),
            "unmatched_httpx_request_count": len(set(httpx_wait_by_request) - set(queue_by_request)),
            "pearson_queue_vs_httpx_wait_response_headers": pearson(queue_values, httpx_wait_values),
            "httpx_wait_response_headers_minus_queue_ms": summarize(header_wait_minus_queue),
            "queue_share_of_httpx_wait_response_headers_avg_pct": (
                round(float(queue_avg) / float(httpx_wait_avg) * 100, 2)
                if queue_avg is not None and httpx_wait_avg not in (None, 0)
                else None
            ),
            "average_boundary_note": (
                "Queue share compares population averages. Pearson and delta are "
                "computed after joining requests by benchmark_request_id."
            ),
        }
        expected_requests = int(level.get("total_messages") or 0)
        warnings: list[str] = []
        if len(level_rows) != expected_requests:
            warnings.append(
                f"Expected {expected_requests} queue samples but found {len(level_rows)} "
                f"for phase {expected_phase}."
            )
        if len(matched_ids) != expected_requests:
            warnings.append(
                f"Queue/HTTPX join matched {len(matched_ids)} of {expected_requests} requests."
            )
        analysis["per_level"].append(
            {
                "concurrency": concurrency,
                "phase": expected_phase,
                "expected_request_count": expected_requests,
                "sample_count": len(level_rows),
                "queue_wait_ms": queue_summary,
                "distribution_summary": distribution_summary,
                "worker_distribution": worker_distribution,
                "thread_distribution": thread_distribution,
                "request_correlation": request_correlation,
                "warnings": warnings,
            }
        )

    analysis["sample_count"] = sum(
        int(item.get("sample_count") or 0)
        for item in analysis["per_level"]
    )
    analysis["expected_request_count"] = sum(
        int(item.get("expected_request_count") or 0)
        for item in analysis["per_level"]
    )
    analysis["missing_sample_count"] = max(
        0,
        analysis["expected_request_count"] - analysis["sample_count"],
    )
    analysis["available"] = analysis["sample_count"] > 0
    if not analysis["available"]:
        analysis["warnings"].append(
            "No measured send_concurrency_<N> gthread queue samples were found for the run_id."
        )

    report["gunicorn_gthread_queue_analysis"] = analysis
    with args.json_report.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
