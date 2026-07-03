#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def avg(row: dict[str, Any], key: str) -> Any:
    return (row.get(key) or {}).get("avg")


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")


def write_report(report: dict[str, Any], output_md: Path) -> None:
    rows = (report.get("request_gap_analysis") or {}).get("per_level") or []
    rows = [row for row in rows if row.get("endpoint")]
    rows.sort(key=lambda row: (str(row.get("endpoint")), int(row.get("concurrency") or 0)))

    lines = [
        "# Myna Endpoint Gap Comparison",
        "",
        f"**Run ID:** `{report.get('run_id')}`  ",
        f"**Cleanup success:** `{report.get('cleanup_success')}`  ",
        f"**Matched requests:** `{(report.get('request_gap_analysis') or {}).get('matched_request_count')}`  ",
        f"**Unmatched percent:** `{(report.get('request_gap_analysis') or {}).get('unmatched_percent')}`  ",
        "",
        "| endpoint | concurrency | client_avg_ms | gunicorn_avg_ms | client_or_network_gap_avg_ms | gunicorn_outside_view_avg_ms | messages_or_requests_per_second | success_count | failure_count |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        throughput = row.get("requests_per_second", row.get("messages_per_second"))
        lines.append(
            "| {endpoint} | {concurrency} | {client} | {gunicorn} | {gap} | {outside} | {throughput} | {success} | {failure} |".format(
                endpoint=fmt(row.get("endpoint")),
                concurrency=fmt(row.get("concurrency")),
                client=fmt(avg(row, "client_latency_ms")),
                gunicorn=fmt(avg(row, "gunicorn_request_ms")),
                gap=fmt(avg(row, "client_or_network_gap_ms")),
                outside=fmt(avg(row, "gunicorn_outside_view_ms")),
                throughput=fmt(throughput),
                success=fmt(row.get("success_count")),
                failure=fmt(row.get("failure_count")),
            )
        )

    lines.extend(
        [
            "",
            "## Reading The Result",
            "",
            "- If `health` and `whoami` show the same high client/network gap at high concurrency, the bottleneck is likely generic request acceptance, Docker networking, or Gunicorn queueing.",
            "- If only `send_message` shows the high gap, send-message traffic is indirectly creating queueing outside the measured Messenger service timing.",
        ]
    )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-report", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    report = load_json(args.json_report)
    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    write_report(report, output_md)
    print(json.dumps({"output_md": str(output_md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
