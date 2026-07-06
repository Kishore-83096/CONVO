#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s [--root PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

cd "$(resolve_root "$root")"
report_dir="$PWD/benchmark/myna_api_test_reports"
require_dir "$report_dir"

python3 - "$report_dir" <<'PY'
import json, pathlib, re, sys
report_dir = pathlib.Path(sys.argv[1])
files = sorted(
    [p for p in report_dir.iterdir() if p.is_file() and p.suffix in {".json", ".md"} and "cleanup" not in p.name],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
if not files:
    raise SystemExit("No benchmark JSON/MD report files found.")
base = files[0].stem
json_path = report_dir / f"{base}.json"
md_path = report_dir / f"{base}.md"
cleanup_path = report_dir / f"{base}_host_side_messenger_cleanup_status.json"
if not json_path.exists():
    raise SystemExit(f"Latest benchmark JSON is missing. Cannot safely repair report pair: {json_path}")
obj = json.loads(json_path.read_text(encoding="utf-8"))
cleanup = None
if cleanup_path.exists():
    cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
elif obj.get("host_side_messenger_cleanup"):
    cleanup = obj["host_side_messenger_cleanup"]
elif obj.get("cleanup", {}).get("messenger"):
    cleanup = obj["cleanup"]["messenger"]
cleanup_success = bool(cleanup and cleanup.get("success"))
cleanup_text = "True" if obj.get("cleanup_success") is True or cleanup_success else "False"
msg_cleanup_text = "True" if cleanup_success else "False"
cleanup_json = json.dumps(cleanup or {}, indent=2)
cleanup_block = "\n".join([
    "## Host-Side Messenger Cleanup",
    "",
    "```json",
    cleanup_json,
    "```",
    "",
    f"**Messenger messages cleaned:** `{msg_cleanup_text}`  ",
    f"**Messages created by benchmark removed:** `{msg_cleanup_text}`  ",
    f"**Final cleanup success:** `{cleanup_text}`  ",
    "",
])
if md_path.exists():
    md = md_path.read_text(encoding="utf-8")
    md = re.sub(r"\*\*Cleanup success:\*\* `(?:True|False)`", f"**Cleanup success:** `{cleanup_text}`", md)
    if "## Host-Side Messenger Cleanup" in md:
        md = re.sub(r"(?s)## Host-Side Messenger Cleanup.*$", cleanup_block, md)
    else:
        md = md.rstrip() + "\n\n" + cleanup_block
    md_path.write_text(md, encoding="utf-8")
else:
    result = "PASS" if obj.get("passed") is True else "FAIL" if obj.get("passed") is False else "UNKNOWN"
    summary = json.dumps(obj.get("summary") or {}, indent=2)
    md = "\n".join([
        "# Myna Distributed-Pairs Latency Benchmark Report",
        "",
        f"**Result:** {result}  ",
        f"**Run ID:** `{obj.get('run_id', '')}`  ",
        f"**Service URL mode:** `{obj.get('service_url_mode', '')}`  ",
        f"**Identity base URL:** `{obj.get('identity_base_url', '')}`  ",
        f"**Messenger base URL:** `{obj.get('messenger_base_url', '')}`  ",
        f"**Traffic mode:** `{obj.get('traffic_mode', '')}`  ",
        f"**Cleanup success:** `{cleanup_text}`",
        "",
        "## Overall Summary",
        "",
        "```json",
        summary,
        "```",
        "",
        cleanup_block,
    ])
    md_path.write_text(md, encoding="utf-8")
print("")
print("Verified benchmark report pair:")
print(f"  JSON: {json_path}")
print(f"  MD:   {md_path}")
if cleanup_path.exists():
    print(f"  Cleanup: {cleanup_path}")
PY
