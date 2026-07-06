#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/linux-common.sh"

root="$repo_root"
cleanup_status_path=""
json_report_path=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) root="$2"; shift 2 ;;
    --cleanup-status-path) cleanup_status_path="$2"; shift 2 ;;
    --json-report) json_report_path="$2"; shift 2 ;;
    -h|--help) printf 'Usage: %s --cleanup-status-path PATH [--json-report PATH] [--root PATH]\n' "$0"; exit 0 ;;
    *) usage_error "Unknown argument: $1" ;;
  esac
done

[[ -n "$cleanup_status_path" ]] || usage_error "--cleanup-status-path is required"
cd "$(resolve_root "$root")"
report_dir="$PWD/benchmark/myna_api_test_reports"
require_dir "$report_dir"
require_file "$cleanup_status_path"
if [[ -n "$json_report_path" ]]; then
  require_file "$json_report_path"
fi

python3 - "$report_dir" "$cleanup_status_path" "$json_report_path" <<'PY'
import json, pathlib, re, sys
report_dir = pathlib.Path(sys.argv[1])
cleanup_path = pathlib.Path(sys.argv[2])
json_report_arg = sys.argv[3]
cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))

def is_primary_benchmark_report(path):
    name = path.name
    excluded_name_parts = (
        "cleanup_status",
        "cleanup-status",
        "host_side_messenger_cleanup_status",
        "request_gap",
        "realtime_outbox_status",
        "service_runtime_config",
        "runtime_config",
        "validation",
        "runs",
    )
    if any(part in name for part in excluded_name_parts):
        return False
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(obj, dict) and isinstance(obj.get("benchmark"), dict) and isinstance(obj.get("summary"), dict)

if json_report_arg:
    json_path = pathlib.Path(json_report_arg)
    if not is_primary_benchmark_report(json_path):
        raise SystemExit(f"Not a primary benchmark JSON report: {json_path}")
else:
    json_files = sorted(
        [p for p in report_dir.glob("*.json") if is_primary_benchmark_report(p)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not json_files:
        raise SystemExit(f"No primary JSON benchmark report found in {report_dir}")
    json_path = json_files[0]
print(f"Patching JSON report: {json_path.name}")
obj = json.loads(json_path.read_text(encoding="utf-8-sig"))
obj["host_side_messenger_cleanup"] = cleanup
identity_cleanup = (obj.get("cleanup") or {}).get("identity")
identity_success = True if identity_cleanup is None else bool(identity_cleanup.get("success"))
final_success = identity_success and bool(cleanup.get("success"))
obj["cleanup_success"] = final_success
json_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

md_files = sorted(json_path.parent.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
if md_files:
    md_path = md_files[0]
    print(f"Patching Markdown report: {md_path.name}")
    md = md_path.read_text(encoding="utf-8")
    status_text = "True" if cleanup.get("success") else "False"
    message_removed_text = "True" if cleanup.get("message_data_removed") else "False"
    final_text = "True" if final_success else "False"
    section = "\n".join([
        "",
        "## Host-Side Messenger Cleanup",
        "",
        "```json",
        json.dumps(cleanup, indent=2),
        "```",
        "",
        f"**Messenger messages cleaned:** `{message_removed_text}`  ",
        f"**Host-side Messenger cleanup success:** `{status_text}`  ",
        f"**Final cleanup success:** `{final_text}`  ",
        "",
    ])
    if "## Host-Side Messenger Cleanup" in md:
        md = re.sub(r"(?s)## Host-Side Messenger Cleanup.*$", section.lstrip(), md)
    else:
        md = md.rstrip() + "\n" + section
    md = re.sub(r"\*\*Cleanup success:\*\* `(?:True|False)`", f"**Cleanup success:** `{final_text}`", md)
    md_path.write_text(md, encoding="utf-8")

if not final_success:
    raise SystemExit("Final cleanup failed. Report was patched with failure.")
print("Report patched with successful Messenger cleanup.")
PY
