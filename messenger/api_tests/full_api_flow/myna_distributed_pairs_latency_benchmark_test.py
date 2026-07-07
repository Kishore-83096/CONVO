#!/usr/bin/env python3
r"""
Myna distributed-pairs latency/concurrency benchmark.

Why this script exists:
- The old benchmark sends every message from one sender to one recipient in one room.
- That is useful as a hot-room stress test, but it is not realistic app-wide traffic.
- This script creates many independent sender-recipient pairs and sends each concurrent
  message from a different sender to a different recipient in a different direct room.

Traffic model:
- Setup creates N independent pairs: sender_i -> recipient_i.
- Sender_i saves recipient_i in Identity.
- Both users register E2EE devices in Messenger.
- Sender_i claims recipient_i prekeys.
- Optional warmup sends one first message per pair using recipient_contact_id to create
  direct rooms and DirectContactState.
- Benchmark ladder sends at concurrency K using the first K pairs, one message per pair.
  When warmup is enabled, benchmark messages use room_id, matching real existing-chat flow.
- Measured traffic uses one persistent HTTPX AsyncClient per simulated sender/pair.
  Each active user owns an independent one-connection pool, matching many real clients
  better than one shared benchmark-side pool.
- Immediately before each measured level, the selected clients issue an unmeasured
  lightweight Messenger health request so their HTTP/1.1 connections are hot.
- A coordinated start gate releases all selected users together. Per-request latency
  starts after gate release when that user's request is dispatched, while dispatch skew
  is reported separately so load-generator scheduling cannot hide inside server latency.

Install:
    pip install httpx cryptography

Run from messenger root, next to manage.py:
    python .\api_tests\full_api_flow\myna_distributed_pairs_latency_benchmark_test.py

URL modes:
    # Local Python/Daphne defaults.
    $env:MYNA_SERVICE_URL_MODE="local"

    # Docker defaults. Override the per-service Docker URLs if you mapped
    # different host ports. Docker containers should be named
    # identity-service-local and messenger-service-local for container stats
    # and cleanup defaults.
    $env:MYNA_SERVICE_URL_MODE="docker"
    $env:MYNA_DOCKER_IDENTITY_BASE_URL="http://127.0.0.1:5000"
    $env:MYNA_DOCKER_MESSENGER_BASE_URL="http://127.0.0.1:8000"

    # Explicit URLs always win over URL mode.
    $env:MYNA_IDENTITY_BASE_URL="http://127.0.0.1:5000"
    $env:MYNA_MESSENGER_BASE_URL="http://127.0.0.1:8000"

Important local-dev note:
    For 100 pairs this script creates 200 Identity users and 100 contacts. If your local
    Identity service rate limits register/contact/delete APIs, temporarily disable local
    rate limiting or run smaller levels first, for example MYNA_BENCHMARK_LEVELS=1,5,10.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import random
import statistics
import subprocess
import sys
import time
import traceback
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlsplit, urlunsplit

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

try:
    import httpx
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: pip install httpx") from exc

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: pip install cryptography") from exc


def normalize_report_path_for_current_os(path_value: str) -> str:
    path_text = str(path_value).strip()
    if sys.platform.startswith("linux") and len(path_text) >= 3 and path_text[1:3] in (":\\", ":/"):
        drive = path_text[0].lower()
        rest = path_text[3:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return path_text


DEFAULT_REPORT_ROOT = normalize_report_path_for_current_os(os.getenv("MYNA_REPORT_ROOT", r"D:\VENV\PARROT-V2\files"))
DEFAULT_REPORT_DIR = str(Path(DEFAULT_REPORT_ROOT) / "myna_api_test_reports")


SERVICE_URL_MODE = os.getenv("MYNA_SERVICE_URL_MODE", "local").strip().lower()
SUPPORTED_SERVICE_URL_MODES = {"local", "docker"}
if SERVICE_URL_MODE not in SUPPORTED_SERVICE_URL_MODES:
    known_modes = ", ".join(sorted(SUPPORTED_SERVICE_URL_MODES))
    raise SystemExit(
        f"Unknown MYNA_SERVICE_URL_MODE={SERVICE_URL_MODE!r}. "
        f"Use one of: {known_modes}."
    )

IDENTITY_BASE_URL_SOURCE = (
    "MYNA_IDENTITY_BASE_URL"
    if os.getenv("MYNA_IDENTITY_BASE_URL")
    else f"MYNA_{SERVICE_URL_MODE.upper()}_IDENTITY_BASE_URL/default"
)
MESSENGER_BASE_URL_SOURCE = (
    "MYNA_MESSENGER_BASE_URL"
    if os.getenv("MYNA_MESSENGER_BASE_URL")
    else f"MYNA_{SERVICE_URL_MODE.upper()}_MESSENGER_BASE_URL/default"
)
SERVICE_URL_PROFILES: dict[str, dict[str, str]] = {
    "local": {
        "IDENTITY_BASE_URL": os.getenv("MYNA_LOCAL_IDENTITY_BASE_URL", "http://127.0.0.1:5000"),
        "MESSENGER_BASE_URL": os.getenv("MYNA_LOCAL_MESSENGER_BASE_URL", "http://127.0.0.1:8000"),
    },
    "docker": {
        "IDENTITY_BASE_URL": os.getenv("MYNA_DOCKER_IDENTITY_BASE_URL", "http://127.0.0.1:5000"),
        "MESSENGER_BASE_URL": os.getenv("MYNA_DOCKER_MESSENGER_BASE_URL", "http://127.0.0.1:8000"),
    },
}


def profile_url(key: str) -> str:
    profile = SERVICE_URL_PROFILES.get(SERVICE_URL_MODE)
    if profile is None:
        known = ", ".join(sorted(SERVICE_URL_PROFILES))
        raise SystemExit(f"Unknown MYNA_SERVICE_URL_MODE={SERVICE_URL_MODE!r}. Use one of: {known}.")
    return profile[key]


CONFIG: dict[str, Any] = {
    "SERVICE_URL_MODE": SERVICE_URL_MODE,
    "IDENTITY_BASE_URL": os.getenv("MYNA_IDENTITY_BASE_URL", profile_url("IDENTITY_BASE_URL")).rstrip("/"),
    "MESSENGER_BASE_URL": os.getenv("MYNA_MESSENGER_BASE_URL", profile_url("MESSENGER_BASE_URL")).rstrip("/"),
    "BENCHMARK_LEVELS": os.getenv("MYNA_BENCHMARK_LEVELS", "1,5,10,20,30,40,50,60,70,80,90,100"),
    "DISTRIBUTED_PAIR_COUNT": int(os.getenv("MYNA_DISTRIBUTED_PAIR_COUNT", "0")),
    "WARMUP_ALL_PAIRS": os.getenv("MYNA_WARMUP_ALL_PAIRS", "true").strip().lower() == "true",
    "REQUEST_TIMEOUT_SECONDS": float(os.getenv("MYNA_REQUEST_TIMEOUT_SECONDS", "30")),
    "SETUP_PAIR_CONCURRENCY": int(os.getenv("MYNA_SETUP_PAIR_CONCURRENCY", "1")),
    "SETUP_PAIR_DELAY_SECONDS": float(os.getenv("MYNA_SETUP_PAIR_DELAY_SECONDS", "0")),
    "BENCHMARK_COOLDOWN_SECONDS": float(os.getenv("MYNA_BENCHMARK_COOLDOWN_SECONDS", "1")),
    "HTTP_MAX_CONNECTIONS": int(os.getenv("MYNA_HTTP_MAX_CONNECTIONS", "300")),
    "HTTP_MAX_KEEPALIVE_CONNECTIONS": int(os.getenv("MYNA_HTTP_MAX_KEEPALIVE_CONNECTIONS", "300")),
    "HTTP_KEEPALIVE_EXPIRY_SECONDS": float(os.getenv("MYNA_HTTP_KEEPALIVE_EXPIRY_SECONDS", "60")),
    "HTTP_POOL_TIMEOUT_SECONDS": float(os.getenv("MYNA_HTTP_POOL_TIMEOUT_SECONDS", "10")),
    "CONNECTION_WARMUP_ENABLED": os.getenv("MYNA_CONNECTION_WARMUP_ENABLED", "true").strip().lower() == "true",
    "CONNECTION_WARMUP_CONCURRENCY": int(os.getenv("MYNA_CONNECTION_WARMUP_CONCURRENCY", "100")),
    "ACTIVE_CLIENT_SETTLE_SECONDS": float(os.getenv("MYNA_ACTIVE_CLIENT_SETTLE_SECONDS", "0.10")),
    "STOP_ON_FIRST_FAILED_LEVEL": os.getenv("MYNA_STOP_ON_FIRST_FAILED_LEVEL", "false").strip().lower() == "true",
    "DOCKER_STATS_ENABLED": os.getenv("MYNA_DOCKER_STATS_ENABLED", "true" if SERVICE_URL_MODE == "docker" else "false").strip().lower() == "true",
    "DOCKER_STATS_INTERVAL_SECONDS": float(os.getenv("MYNA_DOCKER_STATS_INTERVAL_SECONDS", "1")),
    "CLEANUP_MESSENGER_DJANGO": os.getenv("MYNA_CLEANUP_MESSENGER_DJANGO", "true").strip().lower() == "true",
    "CLEANUP_DB_RETRY_ATTEMPTS": int(os.getenv("MYNA_CLEANUP_DB_RETRY_ATTEMPTS", "8")),
    "CLEANUP_DB_RETRY_DELAY_SECONDS": float(os.getenv("MYNA_CLEANUP_DB_RETRY_DELAY_SECONDS", "3")),
    "CLEANUP_IDENTITY_USERS": os.getenv("MYNA_CLEANUP_IDENTITY_USERS", "true").strip().lower() == "true",
    "CLEANUP_IDENTITY_DELAY_SECONDS": float(os.getenv("MYNA_CLEANUP_IDENTITY_DELAY_SECONDS", "0")),
    "IDENTITY_BASE_URL_SOURCE": IDENTITY_BASE_URL_SOURCE,
    "MESSENGER_BASE_URL_SOURCE": MESSENGER_BASE_URL_SOURCE,
    "MESSENGER_DOCKER_CONTAINER": os.getenv(
        "MYNA_MESSENGER_DOCKER_CONTAINER",
        "messenger-service-local" if SERVICE_URL_MODE == "docker" else "",
    ).strip(),
    "IDENTITY_DOCKER_CONTAINER": os.getenv(
        "MYNA_IDENTITY_DOCKER_CONTAINER",
        "identity-service-local" if SERVICE_URL_MODE == "docker" else "",
    ).strip(),
    "REDIS_DOCKER_CONTAINER": os.getenv("MYNA_REDIS_DOCKER_CONTAINER", "redis").strip(),
    "MYSQL_DOCKER_CONTAINER": os.getenv("MYNA_MYSQL_DOCKER_CONTAINER", "").strip(),
    "MESSENGER_PROJECT_ROOT": os.getenv("MYNA_MESSENGER_PROJECT_ROOT", "."),
    "DJANGO_SETTINGS_MODULE": os.getenv("DJANGO_SETTINGS_MODULE", "messenger_config.settings"),
    "REPORT_DIR": normalize_report_path_for_current_os(os.getenv("MYNA_REPORT_DIR", DEFAULT_REPORT_DIR)),
    "REPORT_FILE_PREFIX": os.getenv(
        "MYNA_REPORT_FILE_PREFIX",
        "myna_distributed_pairs_latency",
    ),
    "REPORT_TIMEZONE": os.getenv("MYNA_REPORT_TIMEZONE", "Asia/Kolkata"),
    "WRITE_LEGACY_MARKDOWN": os.getenv(
        "MYNA_WRITE_LEGACY_MARKDOWN",
        "true",
    ).strip().lower() in {"1", "true", "yes", "on"},
}

TEST_RUN_ID = os.getenv("MYNA_TEST_RUN_ID", f"myna-dp-{uuid.uuid4().hex[:10]}")
HTTP_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
PAYLOAD_AAD = b"myna-direct-message-v1"
KEY_WRAP_AAD = b"myna-key-envelope-v1"
KEY_WRAP_INFO = b"myna-test-key-wrap-v1"
HTTPX_REQUEST_HOOK_AT: dict[str, float] = {}
HTTPX_RESPONSE_HOOK_AT: dict[str, float] = {}

for _logger_name in ("asyncio", "httpx", "httpcore"):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)


def local_report_now() -> datetime:
    timezone_name = str(CONFIG.get("REPORT_TIMEZONE") or "").strip()
    if ZoneInfo is not None and timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except Exception:
            pass

    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def log_progress(message: str) -> None:
    print(f"[{local_report_now().strftime('%H:%M:%S')}] {message}", flush=True)


def print_benchmark_level_table_header() -> None:
    print(
        "| Concurrency | Requests | Success | Failure | P95 ms | Msg/s | Overall req total ms | Main Django total ms | Main Django avg ms | Main Django p95 ms |",
        flush=True,
    )
    print(
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        flush=True,
    )


def print_benchmark_level_table_row(level_summary: dict[str, Any]) -> None:
    latency = level_summary.get("latency_ms", {})
    overall = level_summary.get("overall_client_request_time_ms", {})
    main = level_summary.get("main_django_logic_time_ms", {})
    print(
        f"| {level_summary.get('concurrency')} | "
        f"{level_summary.get('total_messages')} | "
        f"{level_summary.get('success_count')} | "
        f"{level_summary.get('failure_count')} | "
        f"{latency.get('p95')} | "
        f"{level_summary.get('messages_per_second')} | "
        f"{overall.get('total')} | "
        f"{main.get('total')} | "
        f"{main.get('avg')} | "
        f"{main.get('p95')} |",
        flush=True,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_report_filename_part(value: Any) -> str:
    text = str(value or "").strip()
    safe_chars = []
    for char in text:
        if char.isalnum() or char in ("-", "_"):
            safe_chars.append(char)
        elif char in (" ", ".", ":", "/", "\\"):
            safe_chars.append("_")

    cleaned = "".join(safe_chars).strip("_")
    return cleaned or "myna_report"


def report_timestamp_for_filename() -> str:
    return local_report_now().strftime("%H-%M-%S_%Y-%m-%d")


def b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def b64decode(text: str) -> bytes:
    normalized = text.strip()
    padding = (-len(normalized)) % 4
    if padding:
        normalized = f"{normalized}{'=' * padding}"
    return base64.urlsafe_b64decode(normalized.encode("ascii"))


def api_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def parse_int_list(value: str) -> list[int]:
    levels: list[int] = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        level = int(part)
        if level < 1:
            raise ValueError(f"Concurrency levels must be >= 1, got {level}")
        levels.append(level)
    if not levels:
        raise ValueError("At least one benchmark level is required.")
    return levels


def normalize_docker_database_url(database_url: str | None, *, docker_host: str) -> str | None:
    if not database_url:
        return database_url

    parsed_url = urlsplit(str(database_url).strip())
    if parsed_url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return str(database_url).strip()

    netloc = docker_host
    if parsed_url.username:
        netloc = parsed_url.username
        if parsed_url.password:
            netloc = f"{netloc}:{parsed_url.password}"
        netloc = f"{netloc}@{docker_host}"
    if parsed_url.port:
        netloc = f"{netloc}:{parsed_url.port}"

    query = urlencode(parse_qsl(parsed_url.query, keep_blank_values=True))
    return urlunsplit(
        (
            parsed_url.scheme,
            netloc,
            parsed_url.path,
            query,
            parsed_url.fragment,
        )
    )


def read_env_file_value(env_file: Path, key: str) -> str | None:
    if not env_file.is_file():
        return None
    prefix = f"{key}="
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or not line.startswith(prefix):
                continue
            value = line[len(prefix) :].strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            return value
    except OSError:
        return None
    return None


def messenger_docker_cleanup_database_url() -> tuple[str | None, str]:
    explicit_url = os.getenv("MYNA_MESSENGER_DOCKER_DATABASE_URL", "").strip()
    if explicit_url:
        source = "MYNA_MESSENGER_DOCKER_DATABASE_URL"
        raw_url = explicit_url
    elif os.getenv("DATABASE_URL", "").strip():
        source = "DATABASE_URL"
        raw_url = os.getenv("DATABASE_URL", "").strip()
    else:
        env_file = Path(str(CONFIG["MESSENGER_PROJECT_ROOT"])).resolve() / ".env.local"
        source = str(env_file)
        raw_url = read_env_file_value(env_file, "DATABASE_URL") or ""

    if not raw_url:
        return None, source

    docker_host = (
        os.getenv("MYNA_MESSENGER_DOCKER_HOST", "").strip()
        or os.getenv("MESSENGER_DOCKER_HOST", "").strip()
        or "host.docker.internal"
    )
    return normalize_docker_database_url(raw_url, docker_host=docker_host), source


def url_hostname(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return urlsplit(value).hostname
    except ValueError:
        return None


def redact_database_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def mysql_connection_params(database_url: str) -> dict[str, Any]:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query))
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "passwd": unquote(parsed.password or ""),
        "db": parsed.path.lstrip("/") or None,
        "connect_timeout": int(query.get("connect_timeout") or 5),
        "charset": query.get("charset") or "utf8mb4",
    }


def capture_mysql_connection_snapshot(stage: str) -> dict[str, Any]:
    captured_at = utc_now_iso()
    database_url, source = messenger_docker_cleanup_database_url()
    base: dict[str, Any] = {
        "stage": stage,
        "captured_at": captured_at,
        "database_url_source": source,
        "database_url_safe": redact_database_url(database_url),
    }
    if not database_url:
        return {**base, "available": False, "error": "No database URL available."}

    try:
        import MySQLdb

        connection = MySQLdb.connect(**mysql_connection_params(database_url))
        try:
            cursor = connection.cursor()
            variables: dict[str, Any] = {}
            status: dict[str, Any] = {}
            for query, target in (
                ("SHOW VARIABLES LIKE 'max_connections'", variables),
                ("SHOW GLOBAL STATUS LIKE 'Threads_connected'", status),
                ("SHOW GLOBAL STATUS LIKE 'Threads_running'", status),
                ("SHOW GLOBAL STATUS LIKE 'Max_used_connections'", status),
                ("SHOW GLOBAL STATUS LIKE 'Connection_errors_max_connections'", status),
                ("SHOW GLOBAL STATUS LIKE 'Aborted_connects'", status),
            ):
                try:
                    cursor.execute(query)
                    row = cursor.fetchone()
                    if row:
                        target[str(row[0])] = row[1]
                except Exception as exc:
                    target[f"error:{query}"] = repr(exc)
            processlist_groups: list[dict[str, Any]] = []
            try:
                cursor.execute(
                    """
                    SELECT USER, HOST, DB, COMMAND, COUNT(*) AS connection_count
                    FROM information_schema.PROCESSLIST
                    GROUP BY USER, HOST, DB, COMMAND
                    ORDER BY connection_count DESC
                    """
                )
                for user, host, db, command, count in cursor.fetchall():
                    processlist_groups.append(
                        {
                            "user": str(user),
                            "host": str(host),
                            "db": str(db or ""),
                            "command": str(command),
                            "connection_count": int(count),
                        }
                    )
            except Exception as exc:
                processlist_groups.append({"error": repr(exc)})
            return {
                **base,
                "available": True,
                "max_connections": int(variables.get("max_connections") or 0),
                "threads_connected": int(status.get("Threads_connected") or 0),
                "threads_running": int(status.get("Threads_running") or 0),
                "max_used_connections": int(status.get("Max_used_connections") or 0),
                "connection_errors_max_connections": int(status.get("Connection_errors_max_connections") or 0),
                "aborted_connects": int(status.get("Aborted_connects") or 0),
                "processlist_groups": processlist_groups,
            }
        finally:
            connection.close()
    except Exception as exc:
        return {
            **base,
            "available": False,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }


async def add_mysql_telemetry(report: dict[str, Any], stage: str) -> None:
    telemetry = report.setdefault(
        "database_connection_telemetry",
        {"available": True, "snapshots": []},
    )
    snapshot = await asyncio.to_thread(capture_mysql_connection_snapshot, stage)
    telemetry.setdefault("snapshots", []).append(snapshot)
    if not snapshot.get("available"):
        telemetry["available"] = False


def decode_jwt_payload_without_verification(token: str) -> dict[str, Any]:
    try:
        payload_part = token.split(".")[1]
        payload_part += "=" * (-len(payload_part) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_part.encode("ascii")))
    except Exception as exc:
        raise RuntimeError("Could not decode JWT payload to read user id.") from exc


def json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


@dataclass
class ApiCallRecord:
    phase: str
    endpoint: str
    method: str
    path: str
    status: int | None
    latency_ms: float
    ok: bool
    error: str | None = None
    benchmark_concurrency: int | None = None


API_CALL_RECORDS: list[ApiCallRecord] = []
SETUP_STEP_RECORDS: list[dict[str, Any]] = []
CURRENT_PHASE = "setup"
CURRENT_BENCHMARK_CONCURRENCY: int | None = None


def set_api_phase(phase: str, concurrency: int | None = None) -> None:
    global CURRENT_PHASE, CURRENT_BENCHMARK_CONCURRENCY
    CURRENT_PHASE = phase
    CURRENT_BENCHMARK_CONCURRENCY = concurrency


def endpoint_name(method: str, url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    path = parsed.path
    method_upper = method.upper()
    mappings = [
        ("POST", "/api/v1/auth/register", "identity_register"),
        ("POST", "/api/v1/auth/login", "identity_login"),
        ("POST", "/api/v1/contacts", "identity_add_contact"),
        ("DELETE", "/api/v1/auth/delete-account", "identity_delete_account"),
        ("GET", "/api/v1/auth/whoami/", "messenger_whoami"),
        ("POST", "/api/v1/e2ee/devices/register/", "messenger_device_register"),
        ("POST", "/api/v1/e2ee/prekey-bundles/claim/", "messenger_prekey_claim"),
        ("POST", "/api/v1/messages/direct/", "messenger_send_direct"),
    ]
    for mapped_method, mapped_path, name in mappings:
        if method_upper == mapped_method and path == mapped_path:
            return name, path
    return f"{method_upper} {path}", path


def record_api_call(method: str, url: str, status: int | None, latency_ms: float, ok: bool, error: str | None = None) -> None:
    name, path = endpoint_name(method, url)
    API_CALL_RECORDS.append(
        ApiCallRecord(
            phase=CURRENT_PHASE,
            endpoint=name,
            method=method.upper(),
            path=path,
            status=status,
            latency_ms=round(latency_ms, 2),
            ok=ok,
            error=error,
            benchmark_concurrency=CURRENT_BENCHMARK_CONCURRENCY,
        )
    )


def run_command_for_snapshot(command: list[str], timeout_seconds: float = 5) -> dict[str, Any]:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "ok": process.returncode == 0,
            "returncode": process.returncode,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
        }
    except FileNotFoundError as exc:
        return {"ok": False, "error": f"command not found: {command[0]}", "detail": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": "command timed out", "detail": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


def docker_container_is_running(container_name: str) -> bool:
    if not container_name:
        return False
    result = run_command_for_snapshot(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Running}}",
            container_name,
        ]
    )
    return bool(result.get("ok") and result.get("stdout", "").strip().lower() == "true")


def configured_running_docker_containers() -> list[str]:
    if SERVICE_URL_MODE != "docker":
        return []
    names = [
        str(CONFIG["MESSENGER_DOCKER_CONTAINER"]),
        str(CONFIG["IDENTITY_DOCKER_CONTAINER"]),
        str(CONFIG["REDIS_DOCKER_CONTAINER"]),
        str(CONFIG["MYSQL_DOCKER_CONTAINER"]),
    ]
    running = []
    for name in dict.fromkeys(item.strip() for item in names if item and item.strip()):
        if docker_container_is_running(name):
            running.append(name)
    return running


def bytes_to_mb(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / (1024 * 1024), 2)


def parse_percent(value: Any) -> float | None:
    text = str(value or "").strip().rstrip("%")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_docker_size_bytes(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None

    number_text = ""
    unit_text = ""
    for char in text:
        if char.isdigit() or char in (".", "-"):
            number_text += char
        elif not char.isspace():
            unit_text += char

    if not number_text:
        return None

    try:
        number = float(number_text)
    except ValueError:
        return None

    unit = unit_text.lower()
    multipliers = {
        "b": 1,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "tb": 1000**4,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
    }
    return number * multipliers.get(unit, 1)


def parse_docker_pair_bytes(value: Any) -> tuple[float | None, float | None]:
    parts = str(value or "").split("/")
    if len(parts) != 2:
        return None, None
    return (
        parse_docker_size_bytes(parts[0]),
        parse_docker_size_bytes(parts[1]),
    )


def read_linux_meminfo() -> dict[str, Any]:
    meminfo_path = Path("/proc/meminfo")
    if not meminfo_path.exists():
        return {"available": False, "message": "/proc/meminfo is not available on this host."}
    values: dict[str, int] = {}
    for line in meminfo_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            try:
                values[parts[0].rstrip(":")] = int(parts[1]) * 1024
            except ValueError:
                continue
    return {
        "available": True,
        "mem_total_mb": bytes_to_mb(values.get("MemTotal")),
        "mem_available_mb": bytes_to_mb(values.get("MemAvailable")),
        "swap_total_mb": bytes_to_mb(values.get("SwapTotal")),
        "swap_free_mb": bytes_to_mb(values.get("SwapFree")),
    }


def parse_docker_inspect(raw_json: str) -> dict[str, Any]:
    try:
        inspected = json.loads(raw_json)
        if not inspected:
            return {"available": False, "message": "docker inspect returned no objects."}
        item = inspected[0]
        host_config = item.get("HostConfig") or {}
        config = item.get("Config") or {}
        state = item.get("State") or {}
        memory_bytes = host_config.get("Memory") or 0
        nano_cpus = host_config.get("NanoCpus") or 0
        cpu_quota = host_config.get("CpuQuota") or 0
        cpu_period = host_config.get("CpuPeriod") or 0
        effective_cpus = None
        if nano_cpus:
            effective_cpus = round(float(nano_cpus) / 1_000_000_000, 2)
        elif cpu_quota and cpu_period:
            effective_cpus = round(float(cpu_quota) / float(cpu_period), 2)
        return {
            "available": True,
            "id": item.get("Id", "")[:12],
            "image": config.get("Image"),
            "running": bool(state.get("Running")),
            "status": state.get("Status"),
            "docker_memory_limit_bytes": memory_bytes,
            "docker_memory_limit_mb": bytes_to_mb(memory_bytes) if memory_bytes else None,
            "docker_memory_limit_note": "0/null means no per-container memory cap; WSL/Docker VM memory still applies." if not memory_bytes else None,
            "docker_nano_cpus": nano_cpus,
            "docker_cpu_quota": cpu_quota,
            "docker_cpu_period": cpu_period,
            "docker_effective_cpu_limit": effective_cpus,
            "docker_cpu_limit_note": "0/null means no per-container CPU cap; WSL/Docker VM CPU allocation still applies." if not effective_cpus else None,
        }
    except Exception as exc:
        return {"available": False, "error": repr(exc), "raw": raw_json[:500]}


def inspect_container_runtime(container_name: str) -> dict[str, Any]:
    if not container_name:
        return {"available": False, "message": "No container name configured."}

    inspect_result = run_command_for_snapshot(["docker", "inspect", container_name])
    container: dict[str, Any] = {
        "name": container_name,
        "inspect": parse_docker_inspect(inspect_result["stdout"]) if inspect_result.get("ok") else inspect_result,
    }

    proc_result = run_command_for_snapshot([
        "docker",
        "exec",
        container_name,
        "sh",
        "-c",
        (
            "printf '{\"cpu_count\":'; "
            "(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || printf 'null'); "
            "printf ',\"proc_mem_total_mb\":'; "
            "awk '/MemTotal/ {printf \"%.2f\", $2/1024}' /proc/meminfo; "
            "printf ',\"proc_mem_available_mb\":'; "
            "awk '/MemAvailable/ {printf \"%.2f\", $2/1024}' /proc/meminfo; "
            "printf ',\"proc_swap_total_mb\":'; "
            "awk '/SwapTotal/ {printf \"%.2f\", $2/1024}' /proc/meminfo; "
            "printf '}\\n'"
        ),
    ])
    if proc_result.get("ok"):
        try:
            container["inside_container"] = json.loads(proc_result["stdout"])
        except Exception:
            container["inside_container"] = proc_result
    else:
        container["inside_container"] = proc_result
    return container


def collect_runtime_environment_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "python_process": {
            "platform": sys.platform,
            "executable": sys.executable,
            "cpu_count_seen_by_test_runner": os.cpu_count(),
            "meminfo": read_linux_meminfo(),
        },
        "docker": {
            "service_url_mode": SERVICE_URL_MODE,
            "docker_version": run_command_for_snapshot(["docker", "--version"]),
        },
    }
    if SERVICE_URL_MODE == "docker":
        configured = {
            "messenger": str(CONFIG["MESSENGER_DOCKER_CONTAINER"]),
            "identity": str(CONFIG["IDENTITY_DOCKER_CONTAINER"]),
            "redis": str(CONFIG["REDIS_DOCKER_CONTAINER"]),
            "mysql": str(CONFIG["MYSQL_DOCKER_CONTAINER"]),
        }
        snapshot["docker"]["configured_containers"] = configured
        snapshot["docker"]["running_containers_for_stats"] = configured_running_docker_containers()
        snapshot["docker"]["containers"] = {
            role: inspect_container_runtime(name)
            for role, name in configured.items()
            if name
        }
    return snapshot


@dataclass
class DockerStatsRecord:
    phase: str
    timestamp: str
    container_id: str
    name: str
    cpu_percent: float | None
    mem_usage_mb: float | None
    mem_limit_mb: float | None
    mem_percent: float | None
    net_rx_mb: float | None
    net_tx_mb: float | None
    block_read_mb: float | None
    block_write_mb: float | None
    pids: int | None
    raw: dict[str, Any] = field(default_factory=dict)


def docker_stats_container_names() -> list[str]:
    if SERVICE_URL_MODE != "docker" or not CONFIG["DOCKER_STATS_ENABLED"]:
        return []
    return configured_running_docker_containers()


def parse_docker_stats_row(phase: str, row: dict[str, Any]) -> DockerStatsRecord:
    mem_usage_bytes, mem_limit_bytes = parse_docker_pair_bytes(row.get("MemUsage"))
    net_rx_bytes, net_tx_bytes = parse_docker_pair_bytes(row.get("NetIO"))
    block_read_bytes, block_write_bytes = parse_docker_pair_bytes(row.get("BlockIO"))
    pids = None
    try:
        pids = int(str(row.get("PIDs") or "").strip())
    except ValueError:
        pass

    return DockerStatsRecord(
        phase=phase,
        timestamp=utc_now_iso(),
        container_id=str(row.get("ID") or row.get("Container") or ""),
        name=str(row.get("Name") or ""),
        cpu_percent=parse_percent(row.get("CPUPerc")),
        mem_usage_mb=bytes_to_mb(int(mem_usage_bytes)) if mem_usage_bytes is not None else None,
        mem_limit_mb=bytes_to_mb(int(mem_limit_bytes)) if mem_limit_bytes is not None else None,
        mem_percent=parse_percent(row.get("MemPerc")),
        net_rx_mb=bytes_to_mb(int(net_rx_bytes)) if net_rx_bytes is not None else None,
        net_tx_mb=bytes_to_mb(int(net_tx_bytes)) if net_tx_bytes is not None else None,
        block_read_mb=bytes_to_mb(int(block_read_bytes)) if block_read_bytes is not None else None,
        block_write_mb=bytes_to_mb(int(block_write_bytes)) if block_write_bytes is not None else None,
        pids=pids,
        raw=row,
    )


def collect_docker_stats_snapshot(phase: str, container_names: list[str]) -> tuple[list[DockerStatsRecord], str | None]:
    if not container_names:
        return [], None

    try:
        process = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", *container_names],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return [], repr(exc)

    if process.returncode != 0:
        return [], (process.stderr or process.stdout or f"docker stats exited {process.returncode}").strip()

    records = []
    errors = []
    for line in process.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(parse_docker_stats_row(phase, json.loads(line)))
        except Exception as exc:
            errors.append(f"{line[:200]}: {exc!r}")

    return records, "; ".join(errors) if errors else None


def summarize_number(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(statistics.mean(values), 2),
    }


def summarize_counter(values: list[float]) -> dict[str, Any]:
    summary = summarize_number(values)
    if values:
        summary["first"] = round(values[0], 2)
        summary["last"] = round(values[-1], 2)
        summary["delta"] = round(values[-1] - values[0], 2)
    else:
        summary["first"] = None
        summary["last"] = None
        summary["delta"] = None
    return summary


def summarize_docker_stats(records: list[DockerStatsRecord]) -> dict[str, Any]:
    by_phase: dict[str, list[DockerStatsRecord]] = {}
    for record in records:
        by_phase.setdefault(record.phase, []).append(record)

    def build(items: list[DockerStatsRecord]) -> dict[str, Any]:
        by_container: dict[str, list[DockerStatsRecord]] = {}
        for item in items:
            by_container.setdefault(item.name or item.container_id, []).append(item)

        containers = {}
        for name, container_items in sorted(by_container.items()):
            containers[name] = {
                "sample_count": len(container_items),
                "container_id": next((item.container_id for item in container_items if item.container_id), None),
                "cpu_percent": summarize_number([item.cpu_percent for item in container_items if item.cpu_percent is not None]),
                "mem_usage_mb": summarize_number([item.mem_usage_mb for item in container_items if item.mem_usage_mb is not None]),
                "mem_limit_mb": summarize_number([item.mem_limit_mb for item in container_items if item.mem_limit_mb is not None]),
                "mem_percent": summarize_number([item.mem_percent for item in container_items if item.mem_percent is not None]),
                "net_rx_mb": summarize_counter([item.net_rx_mb for item in container_items if item.net_rx_mb is not None]),
                "net_tx_mb": summarize_counter([item.net_tx_mb for item in container_items if item.net_tx_mb is not None]),
                "block_read_mb": summarize_counter([item.block_read_mb for item in container_items if item.block_read_mb is not None]),
                "block_write_mb": summarize_counter([item.block_write_mb for item in container_items if item.block_write_mb is not None]),
                "pids": summarize_number([float(item.pids) for item in container_items if item.pids is not None]),
            }
        return {"sample_count": len(items), "containers": containers}

    return {
        "enabled": bool(CONFIG["DOCKER_STATS_ENABLED"]),
        "interval_seconds": float(CONFIG["DOCKER_STATS_INTERVAL_SECONDS"]),
        "container_names": docker_stats_container_names(),
        "total_sample_rows": len(records),
        "overall": build(records),
        "by_phase": {phase: build(items) for phase, items in sorted(by_phase.items())},
    }


class DockerStatsSampler:
    def __init__(self) -> None:
        self.container_names = docker_stats_container_names()
        self.interval_seconds = max(0.2, float(CONFIG["DOCKER_STATS_INTERVAL_SECONDS"]))
        self.records: list[DockerStatsRecord] = []
        self.errors: list[dict[str, Any]] = []
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.container_names)

    async def start(self, phase: str) -> None:
        if not self.enabled or self._task is not None:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._sample_loop(phase))

    async def stop(self) -> None:
        if self._task is None or self._stop_event is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None
        self._stop_event = None

    async def _sample_loop(self, phase: str) -> None:
        while True:
            records, error = await asyncio.to_thread(
                collect_docker_stats_snapshot,
                phase,
                self.container_names,
            )
            self.records.extend(records)
            if error:
                self.errors.append({"phase": phase, "error": error, "at": utc_now_iso()})

            if self._stop_event is None:
                return
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                return
            except asyncio.TimeoutError:
                continue

    def summary(self) -> dict[str, Any]:
        summary = summarize_docker_stats(self.records)
        summary["errors"] = self.errors[:20]
        return summary

    def phase_summary(self, phase: str) -> dict[str, Any]:
        return summarize_docker_stats([record for record in self.records if record.phase == phase])


def _latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "min": None,
            "max": None,
            "avg": None,
            "median": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
        }
    values = sorted(values)
    def pct(p: float) -> float:
        if len(values) == 1:
            return values[0]
        rank = (len(values) - 1) * p
        lower = int(rank)
        upper = min(lower + 1, len(values) - 1)
        weight = rank - lower
        return values[lower] * (1 - weight) + values[upper] * weight

    return {
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "p50": round(pct(0.50), 2),
        "p75": round(pct(0.75), 2),
        "p90": round(pct(0.90), 2),
        "p95": round(pct(0.95), 2),
        "p99": round(pct(0.99), 2),
    }


def _timing_spent_summary(values: list[float]) -> dict[str, Any]:
    result = _latency_summary(values)
    result["total"] = round(sum(values), 2) if values else None
    return result


def summarize_api_calls(records: list[ApiCallRecord]) -> dict[str, Any]:
    def build(items: list[ApiCallRecord]) -> dict[str, Any]:
        statuses: dict[str, int] = {}
        for item in items:
            key = str(item.status or "exception")
            statuses[key] = statuses.get(key, 0) + 1
        return {
            "count": len(items),
            "success_count": sum(1 for item in items if item.ok),
            "failure_count": sum(1 for item in items if not item.ok),
            "status_counts": statuses,
            "latency_ms": _latency_summary([item.latency_ms for item in items]),
            "sample_errors": [item.error for item in items if item.error][:10],
        }

    by_endpoint: dict[str, list[ApiCallRecord]] = {}
    by_level: dict[str, dict[str, list[ApiCallRecord]]] = {}
    for item in records:
        by_endpoint.setdefault(item.endpoint, []).append(item)
        level_key = str(item.benchmark_concurrency) if item.benchmark_concurrency is not None else "setup_cleanup"
        by_level.setdefault(level_key, {}).setdefault(item.endpoint, []).append(item)

    return {
        "total_recorded_api_calls": len(records),
        "by_endpoint": {key: build(items) for key, items in sorted(by_endpoint.items())},
        "by_concurrency_level": {
            level: {endpoint: build(items) for endpoint, items in sorted(endpoints.items())}
            for level, endpoints in sorted(by_level.items(), key=lambda kv: (int(kv[0]) if kv[0].isdigit() else 999999, kv[0]))
        },
        "raw_records_sample": [item.__dict__ for item in records[:200]],
    }


async def checked_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    expected_statuses: set[int] | None = None,
) -> dict[str, Any]:
    headers = dict(HTTP_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    start = time.perf_counter()
    response: httpx.Response | None = None
    try:
        response = await client.request(method, url, json=json_body, headers=headers)
        latency_ms = (time.perf_counter() - start) * 1000
        payload = json_or_text(response)
        expected = expected_statuses or set(range(200, 300))
        ok = response.status_code in expected and isinstance(payload, dict) and payload.get("success") is not False
        record_api_call(method, url, response.status_code, latency_ms, ok)
        if response.status_code not in expected:
            raise RuntimeError(f"{method} {url} failed with HTTP {response.status_code}: {payload}")
        if not isinstance(payload, dict):
            raise RuntimeError(f"{method} {url} returned non-JSON response: {payload}")
        if payload.get("success") is False:
            raise RuntimeError(f"{method} {url} returned API failure: {payload}")
        return payload
    except Exception as exc:
        if response is None:
            latency_ms = (time.perf_counter() - start) * 1000
            record_api_call(method, url, None, latency_ms, False, repr(exc))
        raise


async def probe_public_endpoint(
    client: httpx.AsyncClient,
    *,
    service: str,
    base_url: str,
    path: str,
) -> dict[str, Any]:
    url = api_url(base_url, path)
    start = time.perf_counter()
    response: httpx.Response | None = None
    try:
        response = await client.get(url, headers=HTTP_HEADERS)
        latency_ms = (time.perf_counter() - start) * 1000
        payload = json_or_text(response)
        ok = 200 <= response.status_code < 300
        record_api_call("GET", url, response.status_code, latency_ms, ok)
        return {
            "service": service,
            "base_url": base_url,
            "health_url": url,
            "ok": ok,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 2),
            "response": payload,
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        record_api_call(
            "GET",
            url,
            response.status_code if response is not None else None,
            latency_ms,
            False,
            repr(exc),
        )
        return {
            "service": service,
            "base_url": base_url,
            "health_url": url,
            "ok": False,
            "status_code": response.status_code if response is not None else None,
            "latency_ms": round(latency_ms, 2),
            "error": repr(exc),
        }


async def preflight_service_urls(client: httpx.AsyncClient) -> dict[str, Any]:
    set_api_phase("preflight_service_urls", None)
    log_progress(
        "Service URL mode="
        f"{CONFIG['SERVICE_URL_MODE']}; identity={CONFIG['IDENTITY_BASE_URL']}; "
        f"messenger={CONFIG['MESSENGER_BASE_URL']}"
    )
    identity = await probe_public_endpoint(
        client,
        service="identity",
        base_url=CONFIG["IDENTITY_BASE_URL"],
        path="/api/v1/health/",
    )
    messenger = await probe_public_endpoint(
        client,
        service="messenger",
        base_url=CONFIG["MESSENGER_BASE_URL"],
        path="/api/v1/health/",
    )
    result = {
        "mode": CONFIG["SERVICE_URL_MODE"],
        "identity_base_url": CONFIG["IDENTITY_BASE_URL"],
        "messenger_base_url": CONFIG["MESSENGER_BASE_URL"],
        "identity_base_url_source": CONFIG["IDENTITY_BASE_URL_SOURCE"],
        "messenger_base_url_source": CONFIG["MESSENGER_BASE_URL_SOURCE"],
        "identity": identity,
        "messenger": messenger,
        "ok": bool(identity.get("ok") and messenger.get("ok")),
    }
    if SERVICE_URL_MODE == "docker":
        result["docker"] = {
            "configured_containers": {
                "identity": CONFIG["IDENTITY_DOCKER_CONTAINER"],
                "messenger": CONFIG["MESSENGER_DOCKER_CONTAINER"],
                "redis": CONFIG["REDIS_DOCKER_CONTAINER"],
                "mysql": CONFIG["MYSQL_DOCKER_CONTAINER"],
            },
            "running_containers_for_stats": configured_running_docker_containers(),
            "identity_container_running": docker_container_is_running(str(CONFIG["IDENTITY_DOCKER_CONTAINER"])),
            "messenger_container_running": docker_container_is_running(str(CONFIG["MESSENGER_DOCKER_CONTAINER"])),
            "redis_container_running": docker_container_is_running(str(CONFIG["REDIS_DOCKER_CONTAINER"])),
        }
    if not result["ok"]:
        raise RuntimeError(
            "Service URL preflight failed. "
            f"Identity ok={identity.get('ok')} at {identity.get('health_url')}; "
            f"Messenger ok={messenger.get('ok')} at {messenger.get('health_url')}. "
            "Set MYNA_SERVICE_URL_MODE, MYNA_IDENTITY_BASE_URL, or MYNA_MESSENGER_BASE_URL."
        )
    return result


@dataclass
class TestUser:
    role: str
    username: str
    password: str
    token: str
    user_id: str
    full_name: str
    email: str
    contact_number: str
    created_by_test: bool = True


@dataclass
class DeviceMaterial:
    role: str
    device_id: str
    identity_private: x25519.X25519PrivateKey
    identity_public_b64: str
    signed_prekey_public_b64: str
    one_time_prekey_public_b64: str
    registration_id: int
    signed_prekey_id: int
    one_time_prekey_id: int


@dataclass
class PairContext:
    index: int
    sender: TestUser
    recipient: TestUser
    sender_device: DeviceMaterial
    recipient_device: DeviceMaterial
    recipient_contact_id: int
    claimed_recipient_devices: list[dict[str, Any]]
    room_id: str | None = None


@dataclass
class SentMessageRecord:
    sequence: int
    pair_index: int
    client_message_id: str
    plaintext: dict[str, Any]
    payload: dict[str, Any]
    sender_token: str
    response_status: int | None = None
    response_body: Any = None
    latency_ms: float | None = None
    error: str | None = None
    error_type: str | None = None
    semaphore_wait_ms: float | None = None
    client_request_ms: float | None = None
    client_request_hook_delay_ms: float | None = None
    client_to_response_headers_ms: float | None = None
    client_transport_to_response_headers_ms: float | None = None
    client_response_body_read_ms: float | None = None
    httpx_trace_event_at: dict[str, float] = field(
        default_factory=dict,
        repr=False,
    )
    httpx_trace_ms: dict[str, float] = field(
        default_factory=dict,
    )
    httpx_trace_first_event_name: str | None = None
    httpx_trace_used_new_tcp_connection: bool | None = None
    benchmark_request_id: str | None = None
    benchmark_phase: str | None = None
    benchmark_concurrency_header: int | None = None
    load_generator_dispatch_skew_ms: float | None = None

    @property
    def response_data(self) -> dict[str, Any]:
        if not isinstance(self.response_body, dict):
            return {}
        data = self.response_body.get("data")
        return data if isinstance(data, dict) else {}

    @property
    def expected_envelope_count(self) -> int:
        return len(self.payload.get("envelopes") or [])

    @property
    def success_validation_errors(self) -> list[str]:
        errors: list[str] = []
        if self.response_status not in {200, 201}:
            errors.append(f"status must be 200 or 201, got {self.response_status}")
        if not isinstance(self.response_body, dict):
            errors.append("response body must be a JSON object")
            return errors
        if self.response_body.get("success") is not True:
            errors.append("response.success must be true")
        data = self.response_body.get("data")
        if not isinstance(data, dict):
            errors.append("response.data must be a JSON object")
            return errors
        if str(data.get("client_message_id") or "") != self.client_message_id:
            errors.append("response.data.client_message_id must match request.client_message_id")
        if not str(data.get("message_id") or ""):
            errors.append("response.data.message_id is required")
        if not str(data.get("room_id") or ""):
            errors.append("response.data.room_id is required")
        if data.get("room_type") != "direct":
            errors.append("response.data.room_type must be direct")
        envelope_count = data.get("envelope_count")
        if envelope_count != self.expected_envelope_count:
            errors.append(
                "response.data.envelope_count must match request.envelopes length "
                f"({self.expected_envelope_count}), got {envelope_count}"
            )
        if data.get("message_created") is not True and self.response_status == 201:
            errors.append("201 response must have response.data.message_created=true")
        return errors

    @property
    def ok(self) -> bool:
        return not self.success_validation_errors

    @property
    def message_id(self) -> str | None:
        if not self.ok:
            return None
        return str(self.response_data.get("message_id") or "")

    @property
    def room_id(self) -> str | None:
        if not self.ok:
            return None
        return str(self.response_data.get("room_id") or "")

    @property
    def server_timing_ms(self) -> dict[str, float]:
        if not self.ok:
            return {}

        timings = self.response_data.get("server_timing_ms")
        if not isinstance(timings, dict):
            return {}

        parsed: dict[str, float] = {}
        for key, value in timings.items():
            try:
                parsed[str(key)] = float(value)
            except (TypeError, ValueError):
                continue

        return parsed


def make_device_material(role: str) -> DeviceMaterial:
    identity_private = x25519.X25519PrivateKey.generate()
    signed_private = x25519.X25519PrivateKey.generate()
    one_time_private = x25519.X25519PrivateKey.generate()

    def public_b64(private_key: x25519.X25519PrivateKey) -> str:
        return b64encode(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ))

    return DeviceMaterial(
        role=role,
        device_id=str(uuid.uuid4()),
        identity_private=identity_private,
        identity_public_b64=public_b64(identity_private),
        signed_prekey_public_b64=public_b64(signed_private),
        one_time_prekey_public_b64=public_b64(one_time_private),
        registration_id=random.randint(1, 2_147_000_000),
        signed_prekey_id=random.randint(1, 2_147_000_000),
        one_time_prekey_id=random.randint(1, 2_147_000_000),
    )


def load_x25519_public_key(public_key_b64: str) -> x25519.X25519PublicKey:
    raw = b64decode(public_key_b64)
    if len(raw) != 32:
        raise ValueError(
            "X25519 public keys must decode to 32 bytes, "
            f"got {len(raw)} bytes from value length {len(public_key_b64)}"
        )
    return x25519.X25519PublicKey.from_public_bytes(raw)


def get_claimed_device_identity_key(claimed_device: dict[str, Any]) -> str:
    for key in ("identity_key_public", "identity_public_key"):
        value = str(claimed_device.get(key) or "").strip()
        if value:
            try:
                load_x25519_public_key(value)
            except (ValueError, binascii.Error) as exc:
                raise RuntimeError(
                    f"Recipient prekey claim returned invalid {key} "
                    f"for device {claimed_device.get('device_id')}: {exc}"
                ) from exc
            return value

    raise RuntimeError(
        "Recipient prekey claim did not include a valid top-level "
        f"identity_key_public for device {claimed_device.get('device_id')}: "
        f"{claimed_device}"
    )


def derive_wrap_key(private_key: x25519.X25519PrivateKey, peer_public_key: x25519.X25519PublicKey) -> bytes:
    shared_secret = private_key.exchange(peer_public_key)
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=KEY_WRAP_INFO).derive(shared_secret)


def wrap_content_key(
    *,
    content_key: bytes,
    recipient_public_key_b64: str,
    protocol: str,
    sequence: int,
    claimed_prekey: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    ephemeral_private = x25519.X25519PrivateKey.generate()
    recipient_public = load_x25519_public_key(recipient_public_key_b64)
    wrap_key = derive_wrap_key(ephemeral_private, recipient_public)
    nonce = os.urandom(12)
    wrapped = AESGCM(wrap_key).encrypt(nonce, content_key, KEY_WRAP_AAD)
    ephemeral_public_b64 = b64encode(ephemeral_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ))
    metadata: dict[str, Any] = {
        "algorithm": "x25519-aes-256-gcm-test-v1",
        "nonce": b64encode(nonce),
        "ephemeral_public_key": ephemeral_public_b64,
        "kdf": "hkdf-sha256",
        "aad": KEY_WRAP_AAD.decode("ascii"),
        "protocol_hint": protocol,
        "sequence": sequence,
    }
    if claimed_prekey:
        one_time_prekey = claimed_prekey.get("one_time_prekey")
        if isinstance(one_time_prekey, dict):
            metadata["claimed_one_time_prekey_id"] = one_time_prekey.get("key_id")
        signed_prekey = claimed_prekey.get("signed_prekey")
        if isinstance(signed_prekey, dict):
            metadata["signed_prekey_id"] = signed_prekey.get("key_id")
    return b64encode(wrapped), metadata


def encrypt_message_payload(*, plaintext: dict[str, Any], content_key: bytes) -> tuple[str, dict[str, Any]]:
    nonce = os.urandom(12)
    plaintext_bytes = json.dumps(plaintext, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(content_key).encrypt(nonce, plaintext_bytes, PAYLOAD_AAD)
    metadata = {
        "algorithm": "aes-256-gcm-test-v1",
        "nonce": b64encode(nonce),
        "aad": PAYLOAD_AAD.decode("ascii"),
        "content_format": "json",
        "test_run_id": TEST_RUN_ID,
    }
    return b64encode(ciphertext), metadata


async def register_identity_user(client: httpx.AsyncClient, *, role: str, username: str, password: str) -> None:
    await checked_request(
        client,
        "POST",
        api_url(CONFIG["IDENTITY_BASE_URL"], "/api/v1/auth/register"),
        json_body={
            "full_name": f"Myna Distributed Pair {role.title()}",
            "username": username,
            "password": password,
            "confirm_password": password,
        },
        expected_statuses={201},
    )


def setup_failure_reason(exc: Exception) -> str:
    text = str(exc)
    if "failed with HTTP 400" in text:
        return f"setup_api_validation_error_400: {text}"
    if "failed with HTTP 401" in text:
        return f"setup_auth_error_401: {text}"
    if "failed with HTTP 403" in text:
        return f"setup_permission_error_403: {text}"
    if "failed with HTTP 409" in text:
        return f"setup_conflict_409: {text}"
    if "failed with HTTP 503" in text:
        return f"setup_dependency_unavailable_503: {text}"
    if "failed with HTTP 5" in text:
        return f"setup_server_error: {text}"
    if "timed out" in text.lower() or "timeout" in text.lower():
        return f"setup_timeout: {text}"
    if "Prekey" in text or "prekey" in text:
        return f"setup_prekey_error: {text}"
    if "device" in text.lower():
        return f"setup_device_error: {text}"
    return f"setup_exception: {repr(exc)}"


async def run_setup_step(pair_index: int, step: str, awaitable: Any) -> Any:
    started = time.perf_counter()
    try:
        result = await awaitable
        SETUP_STEP_RECORDS.append(
            {
                "pair_index": pair_index,
                "step": step,
                "success": True,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        return result
    except Exception as exc:
        SETUP_STEP_RECORDS.append(
            {
                "pair_index": pair_index,
                "step": step,
                "success": False,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "reason": setup_failure_reason(exc),
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )
        raise


def summarize_setup_step_records(pair_count: int, successful_pair_count: int) -> dict[str, Any]:
    failed = [record for record in SETUP_STEP_RECORDS if not record.get("success")]
    by_step: dict[str, dict[str, int]] = {}
    for record in SETUP_STEP_RECORDS:
        step = str(record.get("step") or "unknown")
        bucket = by_step.setdefault(step, {"success": 0, "failure": 0})
        bucket["success" if record.get("success") else "failure"] += 1

    reason_counts: dict[str, int] = {}
    for record in failed:
        reason = str(record.get("reason") or record.get("error") or "setup_failed")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "pair_count_requested": pair_count,
        "pair_count_successful": successful_pair_count,
        "setup_step_count": len(SETUP_STEP_RECORDS),
        "failed_count": len(failed),
        "by_step": by_step,
        "top_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "failed_samples": failed[:20],
    }


async def login_identity_user(client: httpx.AsyncClient, *, role: str, username: str, password: str) -> TestUser:
    payload = await checked_request(
        client,
        "POST",
        api_url(CONFIG["IDENTITY_BASE_URL"], "/api/v1/auth/login"),
        json_body={"method": "username", "identifier": username, "password": password},
        expected_statuses={200},
    )
    data = payload["data"]
    token = data["access_token"]
    claims = decode_jwt_payload_without_verification(token)
    user = data["user"]
    return TestUser(
        role=role,
        username=username,
        password=password,
        token=token,
        user_id=str(claims.get("sub") or claims.get("identity") or claims.get("user_id") or ""),
        full_name=str(user.get("full_name") or ""),
        email=str(user.get("email") or f"{username}@myna.test"),
        contact_number=str(user.get("contact_number") or ""),
        created_by_test=True,
    )


async def add_recipient_contact(client: httpx.AsyncClient, *, sender: TestUser, recipient: TestUser) -> tuple[int, TestUser]:
    current_sender = sender
    for attempt in range(2):
        try:
            payload = await checked_request(
                client,
                "POST",
                api_url(CONFIG["IDENTITY_BASE_URL"], "/api/v1/contacts"),
                token=current_sender.token,
                json_body={"contact_number": recipient.contact_number, "saved_name": f"DP Recipient {recipient.user_id}"},
                expected_statuses={201},
            )
            return int(payload["data"]["id"]), current_sender
        except RuntimeError as exc:
            if attempt == 0 and "failed with HTTP 401" in str(exc):
                log_progress(
                    "Identity contact add returned 401 during setup; refreshing sender token and retrying once..."
                )
                current_sender = await login_identity_user(
                    client,
                    role=sender.role,
                    username=sender.username,
                    password=sender.password,
                )
                continue
            raise
    raise RuntimeError("Identity contact add retry exhausted.")


async def assert_messenger_auth(client: httpx.AsyncClient, *, user: TestUser) -> None:
    payload = await checked_request(
        client,
        "GET",
        api_url(CONFIG["MESSENGER_BASE_URL"], "/api/v1/auth/whoami/"),
        token=user.token,
        expected_statuses={200},
    )
    if str(payload.get("user_id")) != user.user_id:
        raise RuntimeError(f"Messenger whoami returned unexpected user id: {payload}")


async def register_messenger_device(client: httpx.AsyncClient, *, user: TestUser, material: DeviceMaterial) -> None:
    await checked_request(
        client,
        "POST",
        api_url(CONFIG["MESSENGER_BASE_URL"], "/api/v1/e2ee/devices/register/"),
        token=user.token,
        json_body={
            "device_id": material.device_id,
            "device_name": f"Distributed {material.role} device",
            "platform": "web",
            "registration_id": material.registration_id,
            "identity_key_public": material.identity_public_b64,
            "signed_prekey_id": material.signed_prekey_id,
            "signed_prekey_public": material.signed_prekey_public_b64,
            "signed_prekey_signature": b64encode(os.urandom(64)),
            "key_algorithm": "curve25519",
            "key_bundle_version": 1,
            "one_time_prekeys": [{"key_id": material.one_time_prekey_id, "public_key": material.one_time_prekey_public_b64}],
        },
        expected_statuses={200, 201},
    )


async def claim_recipient_prekey_bundles(
    client: httpx.AsyncClient,
    *,
    sender: TestUser,
    recipient_contact_id: int,
) -> tuple[list[dict[str, Any]], TestUser]:
    current_sender = sender
    for attempt in range(2):
        try:
            payload = await checked_request(
                client,
                "POST",
                api_url(CONFIG["MESSENGER_BASE_URL"], "/api/v1/e2ee/prekey-bundles/claim/"),
                token=current_sender.token,
                json_body={"recipient_contact_id": recipient_contact_id},
                expected_statuses={200},
            )
            devices = payload["data"]["devices"]
            if not devices:
                raise RuntimeError("Recipient prekey claim returned no devices.")
            return devices, current_sender
        except RuntimeError as exc:
            if attempt == 0 and (
                "failed with HTTP 401" in str(exc)
                or "failed with HTTP 403" in str(exc)
                or "failed with HTTP 503" in str(exc)
            ):
                log_progress(
                    "Messenger prekey claim failed during setup; refreshing sender token and retrying once..."
                )
                await asyncio.sleep(1)
                current_sender = await login_identity_user(
                    client,
                    role=sender.role,
                    username=sender.username,
                    password=sender.password,
                )
                continue
            raise
    raise RuntimeError("Messenger prekey claim retry exhausted.")


async def setup_one_pair(client: httpx.AsyncClient, index: int) -> PairContext:
    suffix = TEST_RUN_ID.replace("-", "_")[-10:]
    sender_username = f"myna_dp_{suffix}_{index:03d}_s"
    recipient_username = f"myna_dp_{suffix}_{index:03d}_r"
    password = f"MynaDP_{suffix}_{index:03d}_Pass123"

    await run_setup_step(
        index,
        "identity_register_sender",
        register_identity_user(client, role=f"sender-{index}", username=sender_username, password=password),
    )
    await run_setup_step(
        index,
        "identity_register_recipient",
        register_identity_user(client, role=f"recipient-{index}", username=recipient_username, password=password),
    )
    sender = await run_setup_step(
        index,
        "identity_login_sender",
        login_identity_user(client, role="sender", username=sender_username, password=password),
    )
    recipient = await run_setup_step(
        index,
        "identity_login_recipient",
        login_identity_user(client, role="recipient", username=recipient_username, password=password),
    )

    await run_setup_step(index, "messenger_whoami_sender", assert_messenger_auth(client, user=sender))
    await run_setup_step(index, "messenger_whoami_recipient", assert_messenger_auth(client, user=recipient))

    reset_result = await run_setup_step(
        index,
        "messenger_reset_state",
        asyncio.to_thread(reset_messenger_state_for_user_ids, [sender.user_id, recipient.user_id]),
    )
    if not reset_result.get("success", False):
        SETUP_STEP_RECORDS.append(
            {
                "pair_index": index,
                "step": "messenger_reset_state",
                "success": False,
                "duration_ms": None,
                "reason": f"setup_messenger_reset_state_failed: {reset_result}",
                "error": repr(reset_result),
            }
        )
        raise RuntimeError(
            "Messenger setup-state reset failed "
            f"for pair {index}: {reset_result}"
        )

    contact_id, sender = await run_setup_step(
        index,
        "identity_add_recipient_contact",
        add_recipient_contact(client, sender=sender, recipient=recipient),
    )

    sender_device = make_device_material(f"sender-{index}")
    recipient_device = make_device_material(f"recipient-{index}")
    await run_setup_step(
        index,
        "messenger_register_sender_device",
        register_messenger_device(client, user=sender, material=sender_device),
    )
    await run_setup_step(
        index,
        "messenger_register_recipient_device",
        register_messenger_device(client, user=recipient, material=recipient_device),
    )
    claimed, sender = await run_setup_step(
        index,
        "messenger_claim_recipient_prekey",
        claim_recipient_prekey_bundles(client, sender=sender, recipient_contact_id=contact_id),
    )

    return PairContext(
        index=index,
        sender=sender,
        recipient=recipient,
        sender_device=sender_device,
        recipient_device=recipient_device,
        recipient_contact_id=contact_id,
        claimed_recipient_devices=claimed,
    )


async def setup_pairs(client: httpx.AsyncClient, pair_count: int) -> list[PairContext]:
    set_api_phase("setup_distributed_pairs")
    log_progress(f"Setting up {pair_count} independent sender-recipient pairs...")
    pairs: list[PairContext] = []
    # Sequential by default because Identity local rate limits can reject bulk register/contact calls.
    # Increase MYNA_SETUP_PAIR_CONCURRENCY only if local rate limits are disabled.
    setup_concurrency = max(1, int(CONFIG["SETUP_PAIR_CONCURRENCY"]))
    delay = float(CONFIG["SETUP_PAIR_DELAY_SECONDS"])

    if setup_concurrency == 1:
        for index in range(1, pair_count + 1):
            log_progress(f"Setting up pair {index}/{pair_count}...")
            pairs.append(await setup_one_pair(client, index))
            if delay > 0 and index < pair_count:
                await asyncio.sleep(delay)
        return pairs

    semaphore = asyncio.Semaphore(setup_concurrency)

    async def guarded(index: int) -> PairContext:
        async with semaphore:
            result = await setup_one_pair(client, index)
            if delay > 0:
                await asyncio.sleep(delay)
            return result

    tasks = [guarded(index) for index in range(1, pair_count + 1)]
    for task in asyncio.as_completed(tasks):
        pair = await task
        pairs.append(pair)
        log_progress(f"Set up pair {len(pairs)}/{pair_count}")
    return sorted(pairs, key=lambda item: item.index)


def build_send_payload_for_pair(*, pair: PairContext, sequence: int, benchmark_concurrency: int | None, force_contact_id: bool = False) -> SentMessageRecord:
    claimed_by_device_id = {str(item["device_id"]): item for item in pair.claimed_recipient_devices}
    client_message_id = str(uuid.uuid4())
    content_key = os.urandom(32)
    plaintext = {
        "test_run_id": TEST_RUN_ID,
        "traffic_mode": "distributed_pairs",
        "sequence": sequence,
        "pair_index": pair.index,
        "benchmark_concurrency": benchmark_concurrency,
        "sender_user_id": pair.sender.user_id,
        "recipient_user_id": pair.recipient.user_id,
        "body": f"Distributed pair latency message #{sequence} pair={pair.index}",
        "created_by_test_at": utc_now_iso(),
    }
    encrypted_payload, encryption_metadata = encrypt_message_payload(plaintext=plaintext, content_key=content_key)

    sender_wrapped_key, sender_wrap_metadata = wrap_content_key(
        content_key=content_key,
        recipient_public_key_b64=pair.sender_device.identity_public_b64,
        protocol="device_sync",
        sequence=sequence,
    )

    envelopes: list[dict[str, Any]] = [
        {
            "recipient_device_id": pair.sender_device.device_id,
            "protocol": "device_sync",
            "session_reference": f"{TEST_RUN_ID}-p{pair.index}-sender-sync-{sequence}",
            "wrapped_message_key": sender_wrapped_key,
            "key_wrap_metadata": sender_wrap_metadata,
            "envelope_version": 1,
        }
    ]

    claimed_recipient_devices = list(pair.claimed_recipient_devices)
    if not any(str(item.get("device_id")) == pair.recipient_device.device_id for item in claimed_recipient_devices):
        claimed_recipient_devices.append(
            {
                "device_id": pair.recipient_device.device_id,
                "identity_key_public": pair.recipient_device.identity_public_b64,
            }
        )

    for recipient_index, claimed_device in enumerate(claimed_recipient_devices, start=1):
        recipient_device_id = str(claimed_device.get("device_id") or "").strip()
        recipient_public_key_b64 = get_claimed_device_identity_key(claimed_device)

        if not recipient_device_id:
            raise RuntimeError(
                "Recipient prekey claim did not include device_id "
                f"for pair {pair.index}: {claimed_device}"
            )

        recipient_wrapped_key, recipient_wrap_metadata = wrap_content_key(
            content_key=content_key,
            recipient_public_key_b64=recipient_public_key_b64,
            protocol="double_ratchet",
            sequence=sequence,
            claimed_prekey=claimed_by_device_id.get(recipient_device_id),
        )
        envelopes.append(
            {
                "recipient_device_id": recipient_device_id,
                "protocol": "double_ratchet",
                "session_reference": (
                    f"{TEST_RUN_ID}-p{pair.index}-recipient-session-"
                    f"{recipient_index}-{sequence}"
                ),
                "wrapped_message_key": recipient_wrapped_key,
                "key_wrap_metadata": recipient_wrap_metadata,
                "envelope_version": 1,
            }
        )

    payload: dict[str, Any] = {
        "sender_device_id": pair.sender_device.device_id,
        "client_message_id": client_message_id,
        "message_type": "text",
        "encrypted_payload": encrypted_payload,
        "encryption_metadata": encryption_metadata,
        "encryption_version": 1,
        "client_sent_at": utc_now_iso(),
        "envelopes": envelopes,
        "recovery_envelopes": [],
    }

    if pair.room_id and not force_contact_id:
        payload["room_id"] = pair.room_id
    else:
        payload["recipient_contact_id"] = pair.recipient_contact_id

    validate_direct_send_payload_shape(payload)
    return SentMessageRecord(
        sequence=sequence,
        pair_index=pair.index,
        client_message_id=client_message_id,
        plaintext=plaintext,
        payload=payload,
        sender_token=pair.sender.token,
    )


def validate_direct_send_payload_shape(payload: dict[str, Any]) -> None:
    has_room_id = bool(payload.get("room_id"))
    has_contact_id = payload.get("recipient_contact_id") is not None
    if has_room_id == has_contact_id:
        raise RuntimeError(
            "Direct send payload must include exactly one recipient selector: "
            "room_id for an existing direct room or recipient_contact_id for "
            "the first direct message."
        )
    required_fields = [
        "sender_device_id",
        "client_message_id",
        "message_type",
        "encrypted_payload",
        "encryption_metadata",
        "encryption_version",
        "client_sent_at",
        "envelopes",
    ]
    missing = [field for field in required_fields if payload.get(field) in (None, "")]
    if missing:
        raise RuntimeError(f"Direct send payload is missing required fields: {missing}")
    if not isinstance(payload.get("encryption_metadata"), dict):
        raise RuntimeError("Direct send payload encryption_metadata must be a JSON object.")
    envelopes = payload.get("envelopes")
    if not isinstance(envelopes, list) or not envelopes:
        raise RuntimeError("Direct send payload requires at least one encrypted device envelope.")
    device_ids = [str(item.get("recipient_device_id") or "") for item in envelopes if isinstance(item, dict)]
    if len(device_ids) != len(envelopes) or any(not item for item in device_ids):
        raise RuntimeError("Every direct send envelope must include recipient_device_id.")
    if len(device_ids) != len(set(device_ids)):
        raise RuntimeError("Direct send payload has duplicate recipient_device_id envelopes.")


async def send_one_message(
    client: httpx.AsyncClient,
    *,
    record: SentMessageRecord,
    semaphore: asyncio.Semaphore,
) -> None:
    semaphore_wait_started = time.perf_counter()

    async with semaphore:
        semaphore_acquired = time.perf_counter()
        record.semaphore_wait_ms = (
            semaphore_acquired - semaphore_wait_started
        ) * 1000

        url = api_url(
            CONFIG["MESSENGER_BASE_URL"],
            "/api/v1/messages/direct/",
        )
        headers = dict(HTTP_HEADERS)
        headers["Authorization"] = f"Bearer {record.sender_token}"

        if record.benchmark_request_id:
            headers["X-Myna-Benchmark-Run-Id"] = TEST_RUN_ID
            headers["X-Myna-Benchmark-Request-Id"] = record.benchmark_request_id
            headers["X-Myna-Benchmark-Phase"] = (
                record.benchmark_phase or CURRENT_PHASE
            )
            headers["X-Myna-Benchmark-Concurrency"] = str(
                record.benchmark_concurrency_header or ""
            )

        # Trace state is per measured request. Clear it in case a record is ever
        # retried or reused by future benchmark code.
        record.httpx_trace_event_at.clear()
        record.httpx_trace_ms.clear()
        record.httpx_trace_first_event_name = None
        record.httpx_trace_used_new_tcp_connection = None

        start = time.perf_counter()
        trace_handler = make_httpx_trace_handler(record)

        try:
            response = await client.post(
                url,
                json=record.payload,
                headers=headers,
                extensions={"trace": trace_handler},
            )
            finished = time.perf_counter()

            record.client_request_ms = (finished - start) * 1000
            record.latency_ms = record.client_request_ms

            apply_httpx_hook_timings(
                record,
                request_started_at=start,
                request_finished_at=finished,
            )
            apply_httpx_trace_timings(
                record,
                request_started_at=start,
                request_finished_at=finished,
            )

            record.response_status = response.status_code
            record.response_body = json_or_text(response)
            record_api_call(
                "POST",
                url,
                response.status_code,
                record.latency_ms,
                record.ok,
            )
        except Exception as exc:
            finished = time.perf_counter()

            record.client_request_ms = (finished - start) * 1000
            record.latency_ms = record.client_request_ms

            apply_httpx_hook_timings(
                record,
                request_started_at=start,
                request_finished_at=finished,
            )
            apply_httpx_trace_timings(
                record,
                request_started_at=start,
                request_finished_at=finished,
            )

            record.error = repr(exc)
            record.error_type = exc.__class__.__name__
            record_api_call(
                "POST",
                url,
                None,
                record.latency_ms,
                False,
                repr(exc),
            )


async def send_concurrently(client: httpx.AsyncClient, *, records: list[SentMessageRecord], concurrency: int) -> None:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    await asyncio.gather(*(send_one_message(client, record=record, semaphore=semaphore) for record in records))


class ActiveUserStartGate:
    """Barrier used only by the load generator to coordinate one request per user."""

    def __init__(self, expected: int) -> None:
        if expected < 1:
            raise ValueError("ActiveUserStartGate expected must be >= 1")
        self.expected = expected
        self._ready_count = 0
        self._ready_lock = asyncio.Lock()
        self._all_ready = asyncio.Event()
        self._release = asyncio.Event()
        self.released_at: float | None = None

    async def arrive_and_wait(self) -> float:
        async with self._ready_lock:
            self._ready_count += 1
            if self._ready_count == self.expected:
                self._all_ready.set()
            elif self._ready_count > self.expected:
                raise RuntimeError("Active-user start gate received too many participants")

        await self._release.wait()
        if self.released_at is None:
            raise RuntimeError("Active-user start gate released without a timestamp")
        return self.released_at

    async def release_when_ready(self) -> float:
        await self._all_ready.wait()
        self.released_at = time.perf_counter()
        self._release.set()
        return self.released_at


async def send_one_active_user_message(
    client: httpx.AsyncClient,
    *,
    record: SentMessageRecord,
    start_gate: ActiveUserStartGate,
) -> None:
    url = api_url(
        CONFIG["MESSENGER_BASE_URL"],
        "/api/v1/messages/direct/",
    )
    headers = dict(HTTP_HEADERS)
    headers["Authorization"] = f"Bearer {record.sender_token}"

    if record.benchmark_request_id:
        headers["X-Myna-Benchmark-Run-Id"] = TEST_RUN_ID
        headers["X-Myna-Benchmark-Request-Id"] = record.benchmark_request_id
        headers["X-Myna-Benchmark-Phase"] = (
            record.benchmark_phase or CURRENT_PHASE
        )
        headers["X-Myna-Benchmark-Concurrency"] = str(
            record.benchmark_concurrency_header or ""
        )

    record.httpx_trace_event_at.clear()
    record.httpx_trace_ms.clear()
    record.httpx_trace_first_event_name = None
    record.httpx_trace_used_new_tcp_connection = None
    trace_handler = make_httpx_trace_handler(record)

    released_at = await start_gate.arrive_and_wait()
    start = time.perf_counter()
    record.load_generator_dispatch_skew_ms = max(
        0.0,
        (start - released_at) * 1000,
    )

    try:
        response = await client.post(
            url,
            json=record.payload,
            headers=headers,
            extensions={"trace": trace_handler},
        )
        finished = time.perf_counter()

        record.client_request_ms = (finished - start) * 1000
        record.latency_ms = record.client_request_ms
        apply_httpx_hook_timings(
            record,
            request_started_at=start,
            request_finished_at=finished,
        )
        apply_httpx_trace_timings(
            record,
            request_started_at=start,
            request_finished_at=finished,
        )
        record.response_status = response.status_code
        record.response_body = json_or_text(response)
        record_api_call(
            "POST",
            url,
            response.status_code,
            record.latency_ms,
            record.ok,
        )
    except Exception as exc:
        finished = time.perf_counter()
        record.client_request_ms = (finished - start) * 1000
        record.latency_ms = record.client_request_ms
        apply_httpx_hook_timings(
            record,
            request_started_at=start,
            request_finished_at=finished,
        )
        apply_httpx_trace_timings(
            record,
            request_started_at=start,
            request_finished_at=finished,
        )
        record.error = repr(exc)
        record.error_type = exc.__class__.__name__
        record_api_call(
            "POST",
            url,
            None,
            record.latency_ms,
            False,
            repr(exc),
        )


async def send_active_users_concurrently(
    clients_by_pair_index: dict[int, httpx.AsyncClient],
    *,
    records: list[SentMessageRecord],
    concurrency: int,
) -> dict[str, Any]:
    if len(records) != concurrency:
        raise RuntimeError(
            f"Active-user benchmark expected {concurrency} records, got {len(records)}"
        )
    pair_indexes = [record.pair_index for record in records]
    if len(pair_indexes) != len(set(pair_indexes)):
        raise RuntimeError(
            "Active-user benchmark requires exactly one measured request per pair/user"
        )
    missing_clients = [
        pair_index
        for pair_index in pair_indexes
        if pair_index not in clients_by_pair_index
    ]
    if missing_clients:
        raise RuntimeError(
            f"Missing dedicated HTTP clients for pair indexes: {missing_clients[:20]}"
        )

    start_gate = ActiveUserStartGate(len(records))
    tasks = [
        asyncio.create_task(
            send_one_active_user_message(
                clients_by_pair_index[record.pair_index],
                record=record,
                start_gate=start_gate,
            )
        )
        for record in records
    ]

    released_at = await start_gate.release_when_ready()
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finished_at = time.perf_counter()

    dispatch_skews = [
        float(record.load_generator_dispatch_skew_ms)
        for record in records
        if record.load_generator_dispatch_skew_ms is not None
    ]
    return {
        "elapsed_ms": round((finished_at - released_at) * 1000, 2),
        "dispatch_skew_ms": _latency_summary(dispatch_skews),
        "participant_count": len(records),
        "start_model": "coordinated_asyncio_event_barrier",
    }


async def warm_active_user_clients(
    clients_by_pair_index: dict[int, httpx.AsyncClient],
    *,
    pairs: list[PairContext],
    phase: str,
) -> dict[str, Any]:
    if not CONFIG["CONNECTION_WARMUP_ENABLED"]:
        return {
            "enabled": False,
            "phase": phase,
            "client_count": len(pairs),
        }

    url = api_url(CONFIG["MESSENGER_BASE_URL"], "/api/v1/health/")

    async def warm_one(pair: PairContext) -> tuple[bool, float, str | None]:
        client = clients_by_pair_index[pair.index]
        started = time.perf_counter()
        try:
            response = await client.get(url)
            elapsed_ms = (time.perf_counter() - started) * 1000
            if not (200 <= response.status_code < 300):
                return False, elapsed_ms, f"HTTP {response.status_code}"
            return True, elapsed_ms, None
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return False, elapsed_ms, repr(exc)

    started = time.perf_counter()
    results = await asyncio.gather(*(warm_one(pair) for pair in pairs))
    elapsed_ms = (time.perf_counter() - started) * 1000
    failures = [
        {"pair_index": pair.index, "error": result[2]}
        for pair, result in zip(pairs, results)
        if not result[0]
    ]
    latencies = [float(result[1]) for result in results]
    summary = {
        "enabled": True,
        "phase": phase,
        "purpose": "establish_or_refresh_one_hot_http_connection_per_selected_active_user",
        "client_model": "one_persistent_async_client_per_pair",
        "client_count": len(pairs),
        "success_count": len(results) - len(failures),
        "failure_count": len(failures),
        "latency_ms": _latency_summary(latencies),
        "total_elapsed_ms": round(elapsed_ms, 2),
        "failed_samples": failures[:20],
        "measured_in_benchmark_summary": False,
    }
    if failures:
        raise RuntimeError(
            f"Active-user connection warmup failed for {len(failures)} clients: "
            f"{failures[:5]}"
        )

    settle_seconds = max(0.0, float(CONFIG["ACTIVE_CLIENT_SETTLE_SECONDS"]))
    if settle_seconds:
        await asyncio.sleep(settle_seconds)
    summary["settle_seconds"] = settle_seconds
    return summary


def assign_benchmark_headers(records: list[SentMessageRecord], *, concurrency: int, phase: str) -> None:
    for ordinal, record in enumerate(records, start=1):
        record.benchmark_phase = phase
        record.benchmark_concurrency_header = concurrency
        record.benchmark_request_id = (
            f"{TEST_RUN_ID}-c{concurrency}-p{record.pair_index}-s{record.sequence}-r{ordinal}"
        )


async def run_connection_warmup(
    client: httpx.AsyncClient,
    *,
    pairs: list[PairContext],
    pairs_by_index: dict[int, PairContext],
    sequence_start: int,
    max_level: int,
) -> tuple[int, dict[str, Any]]:
    if not CONFIG["CONNECTION_WARMUP_ENABLED"]:
        return sequence_start, {"enabled": False}

    concurrency = max(1, int(CONFIG["CONNECTION_WARMUP_CONCURRENCY"] or max_level))
    concurrency = min(concurrency, max(1, len(pairs)))
    phase = f"connection_warmup_{concurrency}"
    records: list[SentMessageRecord] = []
    sequence = sequence_start
    for pair in pairs[:concurrency]:
        sequence += 1
        records.append(
            build_send_payload_for_pair(
                pair=pair,
                sequence=sequence,
                benchmark_concurrency=concurrency,
                force_contact_id=not bool(pair.room_id),
            )
        )

    assign_benchmark_headers(records, concurrency=concurrency, phase=phase)
    set_api_phase(phase, concurrency)
    log_progress(
        f"Connection warmup enabled: sending {len(records)} unmeasured messages at concurrency={concurrency}..."
    )
    started = time.perf_counter()
    await send_concurrently(client, records=records, concurrency=concurrency)
    elapsed_ms = (time.perf_counter() - started) * 1000
    apply_room_ids_to_pairs(records, pairs_by_index)
    summary = summarize_records(records, concurrency="connection_warmup")
    summary["enabled"] = True
    summary["measured_in_benchmark_summary"] = False
    summary["target_concurrency"] = concurrency
    summary["total_send_elapsed_ms"] = round(elapsed_ms, 2)
    add_throughput_metrics(summary, elapsed_ms=elapsed_ms)
    log_progress(
        f"Connection warmup done: success={summary['success_count']}, failure={summary['failure_count']}, "
        f"cooldown={CONFIG['BENCHMARK_COOLDOWN_SECONDS']}s"
    )
    if float(CONFIG["BENCHMARK_COOLDOWN_SECONDS"]) > 0:
        await asyncio.sleep(float(CONFIG["BENCHMARK_COOLDOWN_SECONDS"]))
    return sequence, summary


def apply_room_ids_to_pairs(records: list[SentMessageRecord], pairs_by_index: dict[int, PairContext]) -> None:
    for record in records:
        if record.ok and record.room_id:
            pairs_by_index[record.pair_index].room_id = record.room_id


def failure_reason_for_record(record: SentMessageRecord) -> str:
    if record.error:
        return f"client_exception: {record.error}"

    body = record.response_body if isinstance(record.response_body, dict) else {}
    message = str(body.get("message") or "").strip()
    errors = body.get("errors")
    status = record.response_status

    if record.success_validation_errors:
        return "api_contract_mismatch: " + "; ".join(record.success_validation_errors[:3])
    if status is None:
        return "client_exception: request did not return an HTTP response"
    if status == 400:
        detail = message or json.dumps(errors, default=str) if errors else message
        return f"api_validation_error_400: {detail or 'request rejected by send direct message validation'}"
    if status == 403:
        return f"contact_or_permission_error_403: {message or 'sender is not allowed to send to this recipient'}"
    if status == 409:
        return f"conflict_409: {message or 'direct room, idempotency, or recovery envelope conflict'}"
    if status == 503:
        return f"dependency_unavailable_503: {message or 'identity or messenger dependency unavailable'}"
    if status and status >= 500:
        return f"server_error_{status}: {message or 'send direct message API returned a server error'}"
    return f"http_{status}: {message or 'request failed'}"


def primary_failure_category_for_record(record: SentMessageRecord) -> str | None:
    if record.ok:
        return None

    if record.error_type:
        known_client_errors = {
            "PoolTimeout",
            "ConnectTimeout",
            "ReadTimeout",
            "WriteTimeout",
            "ReadError",
            "ConnectError",
            "RemoteProtocolError",
        }
        if record.error_type in known_client_errors:
            return record.error_type
        return f"client_exception_{record.error_type}"

    body = record.response_body if isinstance(record.response_body, dict) else {}
    errors = body.get("errors") if isinstance(body, dict) else {}
    code = ""
    if isinstance(errors, dict):
        code = str(errors.get("code") or "")

    status = record.response_status
    if status == 503 and code == "database_temporarily_unavailable":
        return "http_503_database_temporarily_unavailable"
    if status is not None:
        return f"http_{status}"

    return "unknown_failure"


def summarize_failure_diagnostics(records: list[SentMessageRecord]) -> dict[str, Any]:
    failed_records = [record for record in records if not record.ok]
    reason_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for record in failed_records:
        reason = failure_reason_for_record(record)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        category = primary_failure_category_for_record(record) or "none"
        category_counts[category] = category_counts.get(category, 0) + 1
    top_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    top_categories = [
        {"category": category, "count": count}
        for category, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "failed_count": len(failed_records),
        "top_primary_failure_categories": top_categories,
        "top_reasons": top_reasons,
        "samples": [
            {
                "sequence": record.sequence,
                "pair_index": record.pair_index,
                "status": record.response_status,
                "primary_failure_category": primary_failure_category_for_record(record),
                "reason": failure_reason_for_record(record),
                "client_message_id": record.client_message_id,
                "benchmark_request_id": record.benchmark_request_id,
                "benchmark_phase": record.benchmark_phase,
                "benchmark_concurrency": record.benchmark_concurrency_header,
                "client_exception_type": record.error_type,
                "api_message": (
                    record.response_body.get("message")
                    if isinstance(record.response_body, dict)
                    else None
                ),
                "api_errors": (
                    record.response_body.get("errors")
                    if isinstance(record.response_body, dict)
                    else None
                ),
                "success_validation_errors": record.success_validation_errors,
            }
            for record in failed_records[:20]
        ],
    }


def summarize_records(records: list[SentMessageRecord], concurrency: Any | None = None) -> dict[str, Any]:
    ok_records = [record for record in records if record.ok]
    failed_records = [record for record in records if not record.ok]
    latencies = [record.latency_ms for record in records if record.latency_ms is not None]
    semaphore_waits = [
        record.semaphore_wait_ms
        for record in records
        if record.semaphore_wait_ms is not None
    ]
    client_request_times = [
        record.client_request_ms
        for record in records
        if record.client_request_ms is not None
    ]
    client_request_hook_delays = [
        record.client_request_hook_delay_ms
        for record in records
        if record.client_request_hook_delay_ms is not None
    ]
    client_to_response_headers = [
        record.client_to_response_headers_ms
        for record in records
        if record.client_to_response_headers_ms is not None
    ]
    client_transport_to_response_headers = [
        record.client_transport_to_response_headers_ms
        for record in records
        if record.client_transport_to_response_headers_ms is not None
    ]
    client_response_body_reads = [
        record.client_response_body_read_ms
        for record in records
        if record.client_response_body_read_ms is not None
    ]
    load_generator_dispatch_skews = [
        record.load_generator_dispatch_skew_ms
        for record in records
        if record.load_generator_dispatch_skew_ms is not None
    ]

    httpx_trace_metric_names = (
        "first_event_delay",
        "connect_tcp",
        "send_request_headers",
        "send_request_body",
        "receive_response_headers",
        "wait_response_headers",
        "receive_response_body",
        "trace_total",
    )
    httpx_trace_summary = {
        metric_name: _latency_summary(
            [
                float(record.httpx_trace_ms[metric_name])
                for record in records
                if metric_name in record.httpx_trace_ms
            ]
        )
        for metric_name in httpx_trace_metric_names
    }

    new_tcp_connection_count = sum(
        record.httpx_trace_used_new_tcp_connection is True
        for record in records
    )
    reused_or_no_connect_event_count = sum(
        record.httpx_trace_used_new_tcp_connection is False
        for record in records
    )
    trace_unavailable_count = sum(
        record.httpx_trace_used_new_tcp_connection is None
        for record in records
    )
    usable_connection_trace_count = (
        new_tcp_connection_count + reused_or_no_connect_event_count
    )
    no_connect_tcp_event_percent = (
        round(
            reused_or_no_connect_event_count
            / usable_connection_trace_count
            * 100,
            2,
        )
        if usable_connection_trace_count
        else None
    )

    first_event_counts: dict[str, int] = {}
    for record in records:
        event_name = record.httpx_trace_first_event_name
        if event_name:
            first_event_counts[event_name] = (
                first_event_counts.get(event_name, 0) + 1
            )

    statuses: dict[str, int] = {}
    for record in records:
        key = str(record.response_status or "exception")
        statuses[key] = statuses.get(key, 0) + 1
    message_ids = [record.message_id for record in ok_records if record.message_id]
    room_ids = [record.room_id for record in ok_records if record.room_id]
    server_timing_values: dict[str, list[float]] = {}
    for record in ok_records:
        for key, value in record.server_timing_ms.items():
            server_timing_values.setdefault(key, []).append(value)
    failed_latencies = [record.latency_ms for record in failed_records if record.latency_ms is not None]
    overall_client_request_times = [float(value) for value in latencies]
    main_django_logic_times = server_timing_values.get("view_total", [])

    return {
        "total_messages": len(records),
        "concurrency": concurrency,
        "success_count": len(ok_records),
        "failure_count": len(failed_records),
        "status_counts": statuses,
        "unique_message_id_count": len(set(message_ids)),
        "duplicate_message_id_count": len(message_ids) - len(set(message_ids)),
        "unique_room_id_count": len(set(room_ids)),
        "room_ids_sample": sorted(set(room_ids))[:20],
        "failure_diagnostics": summarize_failure_diagnostics(records),
        "latency_ms": _latency_summary([float(v) for v in latencies]),
        "benchmark_semaphore_wait_ms": _latency_summary([float(v) for v in semaphore_waits]),
        "client_request_ms": _latency_summary([float(v) for v in client_request_times]),
        "client_request_hook_delay_ms": _latency_summary([float(v) for v in client_request_hook_delays]),
        "client_to_response_headers_ms": _latency_summary([float(v) for v in client_to_response_headers]),
        "client_transport_to_response_headers_ms": _latency_summary([float(v) for v in client_transport_to_response_headers]),
        "client_response_body_read_ms": _latency_summary([float(v) for v in client_response_body_reads]),
        "load_generator_dispatch_skew_ms": _latency_summary([float(v) for v in load_generator_dispatch_skews]),
        "httpx_trace_ms": httpx_trace_summary,
        "httpx_trace_connection_counts": {
            "new_tcp_connection": new_tcp_connection_count,
            "no_connect_tcp_event": reused_or_no_connect_event_count,
            "trace_unavailable": trace_unavailable_count,
            "usable_trace_count": usable_connection_trace_count,
            "no_connect_tcp_event_percent": no_connect_tcp_event_percent,
        },
        "httpx_trace_first_event_counts": dict(
            sorted(first_event_counts.items())
        ),
        "client_timing_semantics": {
            "benchmark_semaphore_wait_ms": (
                "Time spent waiting for the benchmark coroutine semaphore "
                "before calling HTTPX."
            ),
            "client_request_ms": (
                "Time inside HTTPX AsyncClient.post. This may include "
                "HTTPX pool wait, connect, write, server handling, response "
                "headers, and response body read."
            ),
            "httpx_trace_ms": (
                "HTTPX documented trace-extension transport timings. "
                "first_event_delay is request-start to the first observed "
                "httpcore trace event. wait_response_headers is request-body "
                "send completion to response-header receive completion."
            ),
            "client_to_response_headers_ms": (
                "Time from immediately before AsyncClient.post() until the "
                "documented HTTPX response hook fires after response headers. "
                "This still includes pool wait, connect, send, server time, "
                "and response-header transfer."
            ),
            "client_response_body_read_ms": (
                "Time from the documented HTTPX response hook until "
                "AsyncClient.post() returns with the body read."
            ),
            "load_generator_dispatch_skew_ms": (
                "Load-generator scheduling skew from coordinated gate release to "
                "this simulated user's call into AsyncClient.post(). It is reported "
                "separately and is not included in client_latency_ms."
            ),
        },
        "overall_client_request_time_ms": _timing_spent_summary(overall_client_request_times),
        "main_django_logic_time_ms": _timing_spent_summary(main_django_logic_times),
        "failed_client_latency_ms": _latency_summary([float(v) for v in failed_latencies]),
        "server_timing_population": {
            "population": "successful_requests_only",
            "sample_count": len(ok_records),
            "failed_requests_excluded": len(failed_records),
        },
        "server_timing_ms": {
            key: _latency_summary(values)
            for key, values in sorted(
                server_timing_values.items()
            )
        },
        "failed_samples": [
            {
                "sequence": record.sequence,
                "pair_index": record.pair_index,
                "client_message_id": record.client_message_id,
                "status": record.response_status,
                "primary_failure_category": primary_failure_category_for_record(record),
                "error": record.error,
                "client_exception_type": record.error_type,
                "semaphore_wait_ms": round(record.semaphore_wait_ms, 2) if record.semaphore_wait_ms is not None else None,
                "client_request_ms": round(record.client_request_ms, 2) if record.client_request_ms is not None else None,
                "envelope_count": len(record.payload.get("envelopes") or []),
                "expected_request_shape": {
                    "recipient_selector": (
                        "room_id"
                        if record.payload.get("room_id")
                        else "recipient_contact_id"
                    ),
                    "requires_sender_device_id": True,
                    "requires_client_message_id": True,
                    "requires_message_type": "text",
                    "requires_encrypted_payload": True,
                    "requires_encryption_metadata_object": True,
                    "requires_one_envelope_per_active_sender_and_recipient_device": True,
                },
                "success_validation_errors": record.success_validation_errors,
                "body": record.response_body,
            }
            for record in failed_records[:20]
        ],
        "request_records": [
            {
                "sequence": record.sequence,
                "pair_index": record.pair_index,
                "client_message_id": record.client_message_id,
                "benchmark_request_id": record.benchmark_request_id,
                "benchmark_phase": record.benchmark_phase,
                "benchmark_concurrency": record.benchmark_concurrency_header,
                "latency_ms": round(record.latency_ms, 2) if record.latency_ms is not None else None,
                "semaphore_wait_ms": round(record.semaphore_wait_ms, 2) if record.semaphore_wait_ms is not None else None,
                "client_request_ms": round(record.client_request_ms, 2) if record.client_request_ms is not None else None,
                "client_request_hook_delay_ms": round(record.client_request_hook_delay_ms, 2) if record.client_request_hook_delay_ms is not None else None,
                "client_to_response_headers_ms": round(record.client_to_response_headers_ms, 2) if record.client_to_response_headers_ms is not None else None,
                "client_transport_to_response_headers_ms": round(record.client_transport_to_response_headers_ms, 2) if record.client_transport_to_response_headers_ms is not None else None,
                "client_response_body_read_ms": round(record.client_response_body_read_ms, 2) if record.client_response_body_read_ms is not None else None,
                "httpx_trace_first_event_name": record.httpx_trace_first_event_name,
                "httpx_trace_used_new_tcp_connection": record.httpx_trace_used_new_tcp_connection,
                "load_generator_dispatch_skew_ms": round(record.load_generator_dispatch_skew_ms, 2) if record.load_generator_dispatch_skew_ms is not None else None,
                "httpx_trace_ms": {
                    key: round(value, 2)
                    for key, value in sorted(record.httpx_trace_ms.items())
                },
                "status": record.response_status,
                "ok": record.ok,
                "primary_failure_category": primary_failure_category_for_record(record),
                "server_timing_ms": record.server_timing_ms,
                "message_id": record.message_id,
                "room_id": record.room_id,
                "error": record.error,
                "client_exception_type": record.error_type,
            }
            for record in records
        ],
    }


def add_throughput_metrics(summary: dict[str, Any], *, elapsed_ms: float) -> None:
    elapsed_seconds = max(float(elapsed_ms) / 1000.0, 0.001)
    total_requests = int(summary.get("total_messages") or summary.get("total_requests") or 0)
    success_count = int(summary.get("success_count") or 0)
    failure_count = int(summary.get("failure_count") or 0)
    completed_records = success_count + failure_count
    summary["elapsed_seconds"] = round(elapsed_seconds, 4)
    summary["offered_requests_per_second"] = round(total_requests / elapsed_seconds, 2)
    summary["completed_requests_per_second"] = round(completed_records / elapsed_seconds, 2)
    summary["successful_messages_per_second"] = round(success_count / elapsed_seconds, 2)
    summary["failed_requests_per_second"] = round(failure_count / elapsed_seconds, 2)
    summary["messages_per_second"] = summary["successful_messages_per_second"]
    summary["messages_per_second_semantics"] = "successful_messages_per_second"


def send_direct_message_api_contract() -> dict[str, Any]:
    return {
        "method": "POST",
        "path": "/api/v1/messages/direct/",
        "request_json": {
            "recipient_selector": (
                "Use recipient_contact_id for the first message that creates "
                "a direct room; use room_id for later messages in that room. "
                "Do not send both."
            ),
            "required_fields": [
                "sender_device_id",
                "client_message_id",
                "message_type",
                "encrypted_payload",
                "encryption_metadata",
                "encryption_version",
                "client_sent_at",
                "envelopes",
            ],
            "message_type_used_by_benchmark": "text",
            "envelope_rules": [
                "One envelope per active sender and recipient device.",
                "Sender device envelope protocol must be device_sync.",
                "Recipient device envelope protocol must be double_ratchet.",
                "Each envelope requires recipient_device_id, protocol, session_reference, wrapped_message_key, key_wrap_metadata, and envelope_version.",
            ],
            "recovery_envelopes_used_by_benchmark": [],
        },
        "success_response": {
            "http_status": "201 for a newly stored message, 200 for an idempotent existing message.",
            "required_json": {
                "success": True,
                "data": [
                    "room_id",
                    "room_type=direct",
                    "message_id",
                    "client_message_id matching the request",
                    "message_created",
                    "envelope_count matching request.envelopes length",
                    "recovery_envelope_count",
                ],
            },
        },
    }


def collect_report_failure_diagnostics(report: dict[str, Any]) -> dict[str, Any]:
    phases: list[dict[str, Any]] = []

    def add_phase(name: str, summary: dict[str, Any] | None) -> None:
        if not isinstance(summary, dict):
            return
        diagnostics = summary.get("failure_diagnostics") or {}
        failed_count = int(diagnostics.get("failed_count") or summary.get("failure_count") or 0)
        if failed_count <= 0:
            return
        phases.append(
            {
                "phase": name,
                "concurrency": summary.get("concurrency"),
                "failed_count": failed_count,
                "status_counts": summary.get("status_counts"),
                "top_reasons": diagnostics.get("top_reasons", []),
                "samples": diagnostics.get("samples", []),
            }
        )

    add_phase("warmup", report.get("warmup"))
    add_phase("connection_warmup", report.get("connection_warmup"))
    setup = report.get("setup") or {}
    setup_diagnostics = setup.get("failure_diagnostics") if isinstance(setup, dict) else {}
    if isinstance(setup_diagnostics, dict) and int(setup_diagnostics.get("failed_count") or 0) > 0:
        phases.append(
            {
                "phase": "setup_pairs",
                "concurrency": None,
                "failed_count": setup_diagnostics.get("failed_count"),
                "status_counts": None,
                "top_reasons": setup_diagnostics.get("top_reasons", []),
                "samples": setup_diagnostics.get("failed_samples", []),
            }
        )
    for level in (report.get("benchmark") or {}).get("per_level", []) or []:
        add_phase(f"benchmark_concurrency_{level.get('concurrency')}", level)
    add_phase("overall_summary", report.get("summary"))

    cleanup = report.get("cleanup") or {}
    cleanup_failures = []
    for name, result in cleanup.items():
        if isinstance(result, dict) and result.get("success") is False:
            reason = str(result.get("message") or "cleanup_failed")
            cleanup_failures.append(
                {
                    "component": name,
                    "reason": reason,
                    "message": result.get("message"),
                    "traceback": result.get("traceback"),
                }
            )
    if cleanup_failures:
        phases.append(
            {
                "phase": "cleanup",
                "concurrency": None,
                "failed_count": len(cleanup_failures),
                "status_counts": None,
                "top_reasons": [
                    {"reason": item["reason"], "count": 1}
                    for item in cleanup_failures
                ],
                "samples": cleanup_failures,
            }
        )

    return {
        "has_failures": bool(phases or report.get("fatal_error") or cleanup_failures),
        "fatal_error": report.get("fatal_error"),
        "failed_phases": phases,
        "cleanup_failures": cleanup_failures,
    }


def analyze_benchmark_levels(level_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [item for item in level_summaries if item.get("latency_ms") and item["latency_ms"].get("avg") is not None]
    if not usable:
        return {"available": False, "message": "No usable latency data."}

    def metric(item: dict[str, Any], name: str) -> float:
        value = item.get("latency_ms", {}).get(name)
        return float(value) if value is not None else 0.0

    baseline = usable[0]
    baseline_avg = max(metric(baseline, "avg"), 0.001)
    baseline_p95 = max(metric(baseline, "p95") or metric(baseline, "max"), 0.001)
    first_failure = next((item for item in usable if item.get("failure_count", 0) > 0), None)
    first_avg_double = next((item for item in usable if metric(item, "avg") >= baseline_avg * 2), None)
    first_p95_over_3000 = next((item for item in usable if (metric(item, "p95") or metric(item, "max")) >= 3000), None)
    best_throughput = max(usable, key=lambda item: float(item.get("messages_per_second") or 0))
    slowest_avg = max(usable, key=lambda item: metric(item, "avg"))
    slowest_p95 = max(usable, key=lambda item: metric(item, "p95") or metric(item, "max"))
    return {
        "available": True,
        "traffic_mode": "distributed_pairs",
        "baseline_concurrency": baseline.get("concurrency"),
        "baseline_avg_latency_ms": metric(baseline, "avg"),
        "baseline_p95_latency_ms": metric(baseline, "p95") or metric(baseline, "max"),
        "best_throughput_concurrency": best_throughput.get("concurrency"),
        "best_throughput_messages_per_second": best_throughput.get("messages_per_second"),
        "slowest_avg_latency_concurrency": slowest_avg.get("concurrency"),
        "slowest_avg_latency_ms": metric(slowest_avg, "avg"),
        "slowest_p95_latency_concurrency": slowest_p95.get("concurrency"),
        "slowest_p95_latency_ms": metric(slowest_p95, "p95") or metric(slowest_p95, "max"),
        "first_failure_concurrency": first_failure.get("concurrency") if first_failure else None,
        "first_avg_latency_2x_baseline_concurrency": first_avg_double.get("concurrency") if first_avg_double else None,
        "first_p95_latency_over_3000_ms_concurrency": first_p95_over_3000.get("concurrency") if first_p95_over_3000 else None,
    }


def make_httpx_trace_handler(record: SentMessageRecord):
    async def trace(
        event_name: str,
        info: dict[str, Any],
    ) -> None:
        del info
        record.httpx_trace_event_at.setdefault(
            event_name,
            time.perf_counter(),
        )

    return trace


def _httpx_trace_phase_ms(
    events: dict[str, float],
    *phase_names: str,
) -> float | None:
    for phase_name in phase_names:
        started = events.get(f"{phase_name}.started")
        complete = events.get(f"{phase_name}.complete")

        if started is not None and complete is not None:
            return max(
                0.0,
                (complete - started) * 1000,
            )

    return None


def _httpx_trace_event_at(
    events: dict[str, float],
    *event_names: str,
) -> float | None:
    for event_name in event_names:
        value = events.get(event_name)
        if value is not None:
            return value

    return None


def apply_httpx_trace_timings(
    record: SentMessageRecord,
    *,
    request_started_at: float,
    request_finished_at: float,
) -> None:
    events = record.httpx_trace_event_at

    if not events:
        return

    first_event_name, first_event_at = min(
        events.items(),
        key=lambda item: item[1],
    )
    record.httpx_trace_first_event_name = first_event_name
    record.httpx_trace_used_new_tcp_connection = any(
        name.startswith("connection.connect_tcp.")
        for name in events
    )

    record.httpx_trace_ms["first_event_delay"] = max(
        0.0,
        (first_event_at - request_started_at) * 1000,
    )

    phase_specs = {
        "connect_tcp": (
            "connection.connect_tcp",
        ),
        "send_request_headers": (
            "http11.send_request_headers",
            "http2.send_request_headers",
        ),
        "send_request_body": (
            "http11.send_request_body",
            "http2.send_request_body",
        ),
        "receive_response_headers": (
            "http11.receive_response_headers",
            "http11.receive_response",
            "http2.receive_response_headers",
        ),
        "receive_response_body": (
            "http11.receive_response_body",
            "http2.receive_response_body",
        ),
    }

    for metric_name, phase_names in phase_specs.items():
        value = _httpx_trace_phase_ms(
            events,
            *phase_names,
        )
        if value is not None:
            record.httpx_trace_ms[metric_name] = value

    request_send_complete = _httpx_trace_event_at(
        events,
        "http11.send_request_body.complete",
        "http2.send_request_body.complete",
        "http11.send_request_headers.complete",
        "http2.send_request_headers.complete",
    )
    response_headers_complete = _httpx_trace_event_at(
        events,
        "http11.receive_response_headers.complete",
        "http11.receive_response.complete",
        "http2.receive_response_headers.complete",
    )

    if (
        request_send_complete is not None
        and response_headers_complete is not None
    ):
        record.httpx_trace_ms["wait_response_headers"] = max(
            0.0,
            (
                response_headers_complete
                - request_send_complete
            ) * 1000,
        )

    record.httpx_trace_ms["trace_total"] = max(
        0.0,
        (
            min(
                max(events.values()),
                request_finished_at,
            )
            - first_event_at
        ) * 1000,
    )


async def record_httpx_request_hook(request: httpx.Request) -> None:
    request_id = str(
        request.headers.get("X-Myna-Benchmark-Request-Id")
        or ""
    ).strip()
    if request_id:
        HTTPX_REQUEST_HOOK_AT[request_id] = time.perf_counter()


async def record_httpx_response_hook(response: httpx.Response) -> None:
    request_id = str(
        response.request.headers.get("X-Myna-Benchmark-Request-Id")
        or ""
    ).strip()
    if request_id:
        HTTPX_RESPONSE_HOOK_AT[request_id] = time.perf_counter()


def apply_httpx_hook_timings(
    record: SentMessageRecord,
    *,
    request_started_at: float,
    request_finished_at: float,
) -> None:
    request_id = str(record.benchmark_request_id or "").strip()
    if not request_id:
        return

    request_hook_at = HTTPX_REQUEST_HOOK_AT.pop(request_id, None)
    response_hook_at = HTTPX_RESPONSE_HOOK_AT.pop(request_id, None)
    if request_hook_at is not None:
        record.client_request_hook_delay_ms = (
            request_hook_at - request_started_at
        ) * 1000
    if response_hook_at is not None:
        record.client_to_response_headers_ms = (
            response_hook_at - request_started_at
        ) * 1000
        record.client_response_body_read_ms = max(
            0.0,
            (request_finished_at - response_hook_at) * 1000,
        )
        if request_hook_at is not None:
            record.client_transport_to_response_headers_ms = max(
                0.0,
                (response_hook_at - request_hook_at) * 1000,
            )


def pair_user_ids(pairs: list[PairContext]) -> list[str]:
    user_ids = []
    for pair in pairs:
        user_ids.extend([pair.sender.user_id, pair.recipient.user_id])
    return sorted(set(str(item) for item in user_ids if item))


def make_benchmark_http_client() -> httpx.AsyncClient:
    http_limits = httpx.Limits(
        max_connections=int(CONFIG["HTTP_MAX_CONNECTIONS"]),
        max_keepalive_connections=int(CONFIG["HTTP_MAX_KEEPALIVE_CONNECTIONS"]),
        keepalive_expiry=float(CONFIG["HTTP_KEEPALIVE_EXPIRY_SECONDS"]),
    )
    timeout = httpx.Timeout(
        connect=10.0,
        read=float(CONFIG["REQUEST_TIMEOUT_SECONDS"]),
        write=10.0,
        pool=float(CONFIG["HTTP_POOL_TIMEOUT_SECONDS"]),
    )
    return httpx.AsyncClient(
        timeout=timeout,
        limits=http_limits,
        follow_redirects=False,
        event_hooks={
            "request": [record_httpx_request_hook],
            "response": [record_httpx_response_hook],
        },
    )


def invalidate_messenger_user_caches(pairs: list[PairContext]) -> dict[str, Any]:
    user_ids = pair_user_ids(pairs)
    if not user_ids:
        return {"enabled": True, "success": True, "user_count": 0}

    root = Path(str(CONFIG["MESSENGER_PROJECT_ROOT"])).resolve()
    if not (root / "manage.py").exists():
        return {
            "enabled": True,
            "success": False,
            "message": f"manage.py not found at {root}.",
            "user_count": len(user_ids),
        }

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", str(CONFIG["DJANGO_SETTINGS_MODULE"]))

    try:
        import django

        django.setup()
        from apps.e2ee_devices.recovery_services import (
            invalidate_recovery_active_cache_for_user,
        )
        from apps.e2ee_devices.services import (
            invalidate_active_device_cache_for_user,
        )

        for user_id in user_ids:
            invalidate_active_device_cache_for_user(user_id)
            invalidate_recovery_active_cache_for_user(user_id)

        return {
            "enabled": True,
            "success": True,
            "user_count": len(user_ids),
            "cache_types": [
                "active_devices",
                "recovery_active_bundle",
            ],
        }
    except Exception as exc:
        return {
            "enabled": True,
            "success": False,
            "user_count": len(user_ids),
            "message": repr(exc),
            "traceback": traceback.format_exc(),
        }


def reset_messenger_state_for_user_ids(user_ids: list[str]) -> dict[str, Any]:
    normalized_user_ids = sorted(set(str(item) for item in user_ids if item))
    if not normalized_user_ids:
        return {"enabled": True, "success": True, "user_count": 0}

    root = Path(str(CONFIG["MESSENGER_PROJECT_ROOT"])).resolve()
    if not (root / "manage.py").exists():
        return {
            "enabled": True,
            "success": False,
            "message": f"manage.py not found at {root}.",
            "user_count": len(normalized_user_ids),
        }

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", str(CONFIG["DJANGO_SETTINGS_MODULE"]))

    try:
        import django
        from django.db.models import Q

        django.setup()
        from apps.chat_messages.models import ContactDeliveryPolicy, DirectContactState, Message
        from apps.e2ee_devices.models import Device, RecoveryBundle
        from apps.e2ee_devices.recovery_services import (
            invalidate_recovery_active_cache_for_user,
        )
        from apps.e2ee_devices.services import (
            invalidate_active_device_cache_for_user,
        )
        from apps.realtime.models import RealtimeOutboxEvent, RealtimeTicket
        from apps.rooms.models import Room, RoomMember

        for user_id in normalized_user_ids:
            invalidate_active_device_cache_for_user(user_id)
            invalidate_recovery_active_cache_for_user(user_id)

        device_ids = list(
            Device.objects.filter(user_id__in=normalized_user_ids).values_list(
                "id",
                flat=True,
            )
        )
        device_ids = [str(item) for item in device_ids]
        target_groups = [
            f"user.{user_id}"
            for user_id in normalized_user_ids
        ] + [
            f"device.{device_id}"
            for device_id in device_ids
        ]
        room_ids = list(
            RoomMember.objects.filter(user_id__in=normalized_user_ids)
            .values_list("room_id", flat=True)
            .distinct()
        )
        message_ids = list(Message.objects.filter(room_id__in=room_ids).values_list("id", flat=True))

        outbox_deleted, _ = RealtimeOutboxEvent.objects.filter(target_group__in=target_groups).delete()
        tickets_deleted, _ = RealtimeTicket.objects.filter(Q(user_id__in=normalized_user_ids) | Q(device_id__in=device_ids)).delete()
        messages_deleted, _ = Message.objects.filter(id__in=message_ids).delete()
        contact_states_deleted, _ = DirectContactState.objects.filter(Q(owner_user_id__in=normalized_user_ids) | Q(contact_user_id__in=normalized_user_ids)).delete()
        rooms_deleted, _ = Room.objects.filter(id__in=room_ids).delete()
        policies_deleted, _ = ContactDeliveryPolicy.objects.filter(Q(owner_user_id__in=normalized_user_ids) | Q(target_user_id__in=normalized_user_ids)).delete()
        recovery_deleted, _ = RecoveryBundle.objects.filter(user_id__in=normalized_user_ids).delete()
        devices_deleted, _ = Device.objects.filter(Q(user_id__in=normalized_user_ids) | Q(id__in=device_ids)).delete()

        for user_id in normalized_user_ids:
            invalidate_active_device_cache_for_user(user_id)
            invalidate_recovery_active_cache_for_user(user_id)

        return {
            "enabled": True,
            "success": True,
            "user_count": len(normalized_user_ids),
            "device_count_targeted": len(device_ids),
            "room_count_targeted": len(room_ids),
            "message_count_targeted": len(message_ids),
            "deleted": {
                "messages_and_cascades": messages_deleted,
                "direct_contact_states": contact_states_deleted,
                "rooms_and_members": rooms_deleted,
                "devices_and_prekeys": devices_deleted,
                "contact_policies": policies_deleted,
                "recovery_bundles": recovery_deleted,
                "realtime_tickets": tickets_deleted,
                "realtime_outbox_events": outbox_deleted,
            },
            "cache_invalidated": True,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "success": False,
            "user_count": len(normalized_user_ids),
            "message": repr(exc),
            "traceback": traceback.format_exc(),
        }


def cleanup_messenger_with_django(pairs: list[PairContext]) -> dict[str, Any]:
    if not CONFIG["CLEANUP_MESSENGER_DJANGO"]:
        return {"enabled": False, "message": "Messenger Django cleanup disabled."}
    if CONFIG["MESSENGER_DOCKER_CONTAINER"]:
        return cleanup_messenger_with_docker_container(pairs)
    root = Path(str(CONFIG["MESSENGER_PROJECT_ROOT"])).resolve()
    if not (root / "manage.py").exists():
        return {"enabled": True, "success": False, "message": f"manage.py not found at {root}."}
    sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", str(CONFIG["DJANGO_SETTINGS_MODULE"]))
    try:
        import django
        from django.db import OperationalError, close_old_connections, connections
        from django.db.models import Q

        django.setup()
        from apps.chat_messages.models import ContactDeliveryPolicy, DirectContactState, Message
        from apps.e2ee_devices.models import Device, RecoveryBundle
        from apps.realtime.models import RealtimeOutboxEvent, RealtimeTicket
        from apps.rooms.models import Room, RoomMember

        device_ids = []
        user_ids = pair_user_ids(pairs)
        for pair in pairs:
            device_ids.extend([pair.sender_device.device_id, pair.recipient_device.device_id])
        device_ids = sorted(set(str(item) for item in device_ids if item))

        if not user_ids and not device_ids:
            return {"enabled": True, "success": True, "message": "No Messenger IDs to clean."}

        cache_before = invalidate_messenger_user_caches(pairs)
        target_groups = [f"user.{user_id}" for user_id in user_ids] + [f"device.{device_id}" for device_id in device_ids]

        def delete_target_data() -> dict[str, Any]:
            outbox_deleted, _ = RealtimeOutboxEvent.objects.filter(target_group__in=target_groups).delete()
            tickets_deleted, _ = RealtimeTicket.objects.filter(Q(user_id__in=user_ids) | Q(device_id__in=device_ids)).delete()
            room_ids = list(RoomMember.objects.filter(user_id__in=user_ids).values_list("room_id", flat=True).distinct())
            message_ids = list(Message.objects.filter(room_id__in=room_ids).values_list("id", flat=True))
            messages_deleted, _ = Message.objects.filter(id__in=message_ids).delete()
            contact_states_deleted, _ = DirectContactState.objects.filter(Q(owner_user_id__in=user_ids) | Q(contact_user_id__in=user_ids)).delete()
            rooms_deleted, _ = Room.objects.filter(id__in=room_ids).delete()
            policies_deleted, _ = ContactDeliveryPolicy.objects.filter(Q(owner_user_id__in=user_ids) | Q(target_user_id__in=user_ids)).delete()
            recovery_deleted, _ = RecoveryBundle.objects.filter(user_id__in=user_ids).delete()
            devices_deleted, _ = Device.objects.filter(Q(user_id__in=user_ids) | Q(id__in=device_ids)).delete()
            return {
                "room_ids": room_ids,
                "message_ids": message_ids,
                "deleted": {
                    "messages_and_cascades": messages_deleted,
                    "direct_contact_states": contact_states_deleted,
                    "rooms_and_members": rooms_deleted,
                    "devices_and_prekeys": devices_deleted,
                    "contact_policies": policies_deleted,
                    "recovery_bundles": recovery_deleted,
                    "realtime_tickets": tickets_deleted,
                    "realtime_outbox_events": outbox_deleted,
                },
            }

        attempts = max(1, int(CONFIG["CLEANUP_DB_RETRY_ATTEMPTS"]))
        delay_seconds = max(0.0, float(CONFIG["CLEANUP_DB_RETRY_DELAY_SECONDS"]))
        cleanup_attempts = 0
        last_operational_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            cleanup_attempts = attempt
            try:
                close_old_connections()
                connections.close_all()
                deleted_result = delete_target_data()
                break
            except OperationalError as exc:
                if "1040" not in repr(exc) and "Too many connections" not in repr(exc):
                    raise
                last_operational_error = exc
                connections.close_all()
                if attempt >= attempts:
                    raise
                time.sleep(delay_seconds * attempt)
        else:
            raise last_operational_error or RuntimeError("Messenger cleanup retry loop exhausted.")

        cache_after = invalidate_messenger_user_caches(pairs)
        room_ids = deleted_result["room_ids"]
        message_ids = deleted_result["message_ids"]
        return {
            "enabled": True,
            "success": True,
            "user_count": len(user_ids),
            "device_count": len(device_ids),
            "room_count_targeted": len(room_ids),
            "message_count_targeted": len(message_ids),
            "deleted": deleted_result["deleted"],
            "db_cleanup_attempts": cleanup_attempts,
            "cache_invalidated_before_delete": cache_before,
            "cache_invalidated_after_delete": cache_after,
        }
    except Exception as exc:
        return {"enabled": True, "success": False, "message": repr(exc), "traceback": traceback.format_exc()}


def cleanup_messenger_with_docker_container(pairs: list[PairContext]) -> dict[str, Any]:
    container = str(CONFIG["MESSENGER_DOCKER_CONTAINER"]).strip()
    if not container:
        return {"enabled": False, "message": "Messenger Docker cleanup disabled."}

    user_ids = []
    device_ids = []
    for pair in pairs:
        user_ids.extend([pair.sender.user_id, pair.recipient.user_id])
        device_ids.extend([pair.sender_device.device_id, pair.recipient_device.device_id])
    user_ids = sorted(set(str(item) for item in user_ids if item))
    device_ids = sorted(set(str(item) for item in device_ids if item))

    if not user_ids and not device_ids:
        return {"enabled": True, "success": True, "message": "No Messenger IDs to clean."}

    database_url, database_url_source = messenger_docker_cleanup_database_url()
    docker_command = [
        "docker",
        "exec",
        "--workdir",
        "/app",
        "--env",
        f"DJANGO_SETTINGS_MODULE={CONFIG['DJANGO_SETTINGS_MODULE']}",
    ]
    if database_url:
        docker_command.extend(["--env", f"DATABASE_URL={database_url}"])
    docker_command.extend(
        [
            container,
            "python",
            "manage.py",
            "shell",
            "-c",
        ]
    )

    cleanup_code = f"""
import json
from django.db.models import Q
from apps.chat_messages.models import (
    ContactDeliveryPolicy,
    DirectContactState,
    Message,
    MessageKeyEnvelope,
    MessageReceipt,
    MessageRecoveryEnvelope,
)
from apps.e2ee_devices.models import Device, OneTimePreKey, RecoveryBundle
from apps.e2ee_devices.recovery_services import invalidate_recovery_active_cache_for_user
from apps.e2ee_devices.services import invalidate_active_device_cache_for_user
from apps.realtime.models import RealtimeOutboxEvent, RealtimeTicket
from apps.rooms.models import Room, RoomMember

user_ids = {user_ids!r}
device_ids = {device_ids!r}
for user_id in user_ids:
    invalidate_active_device_cache_for_user(user_id)
    invalidate_recovery_active_cache_for_user(user_id)
target_groups = [f"user.{{user_id}}" for user_id in user_ids] + [f"device.{{device_id}}" for device_id in device_ids]
room_ids = list(RoomMember.objects.filter(user_id__in=user_ids).values_list("room_id", flat=True).distinct())
message_ids = list(Message.objects.filter(room_id__in=room_ids).values_list("id", flat=True))

outbox_deleted, _ = RealtimeOutboxEvent.objects.filter(target_group__in=target_groups).delete()
tickets_deleted, _ = RealtimeTicket.objects.filter(Q(user_id__in=user_ids) | Q(device_id__in=device_ids)).delete()
receipts_deleted, _ = MessageReceipt.objects.filter(message_id__in=message_ids).delete()
recovery_envelopes_deleted, _ = MessageRecoveryEnvelope.objects.filter(message_id__in=message_ids).delete()
key_envelopes_deleted, _ = MessageKeyEnvelope.objects.filter(message_id__in=message_ids).delete()
messages_deleted, _ = Message.objects.filter(id__in=message_ids).delete()
contact_states_deleted, _ = DirectContactState.objects.filter(Q(owner_user_id__in=user_ids) | Q(contact_user_id__in=user_ids)).delete()
rooms_deleted, _ = Room.objects.filter(id__in=room_ids).delete()
policies_deleted, _ = ContactDeliveryPolicy.objects.filter(Q(owner_user_id__in=user_ids) | Q(target_user_id__in=user_ids)).delete()
prekeys_deleted, _ = OneTimePreKey.objects.filter(device_id__in=device_ids).delete()
recovery_deleted, _ = RecoveryBundle.objects.filter(user_id__in=user_ids).delete()
devices_deleted, _ = Device.objects.filter(Q(user_id__in=user_ids) | Q(id__in=device_ids)).delete()
for user_id in user_ids:
    invalidate_active_device_cache_for_user(user_id)
    invalidate_recovery_active_cache_for_user(user_id)

print(json.dumps({{
    "user_count": len(user_ids),
    "device_count": len(device_ids),
    "room_count_targeted": len(room_ids),
    "message_count_targeted": len(message_ids),
    "deleted": {{
        "message_receipts": receipts_deleted,
        "message_recovery_envelopes": recovery_envelopes_deleted,
        "message_key_envelopes": key_envelopes_deleted,
        "messages": messages_deleted,
        "direct_contact_states": contact_states_deleted,
        "rooms_and_members": rooms_deleted,
        "devices_and_prekeys": devices_deleted,
        "one_time_prekeys": prekeys_deleted,
        "contact_policies": policies_deleted,
        "recovery_bundles": recovery_deleted,
        "realtime_tickets": tickets_deleted,
        "realtime_outbox_events": outbox_deleted,
    }},
    "cache_invalidated": True,
}}))
"""
    try:
        process = subprocess.run(
            [*docker_command, cleanup_code],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if process.returncode != 0:
            return {
                "enabled": True,
                "success": False,
                "mode": "docker",
                "container": container,
                "database_url_source": database_url_source,
                "database_host": url_hostname(database_url),
                "message": f"docker exec cleanup failed with exit code {process.returncode}.",
                "stdout": process.stdout[-4000:],
                "stderr": process.stderr[-4000:],
            }
        payload = None
        for line in reversed(process.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                payload = json.loads(line)
                break
        if payload is None:
            payload = {"stdout": process.stdout[-4000:]}
        return {
            "enabled": True,
            "success": True,
            "mode": "docker",
            "container": container,
            "database_url_source": database_url_source,
            "database_host": url_hostname(database_url),
            **payload,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "success": False,
            "mode": "docker",
            "container": container,
            "database_url_source": database_url_source,
            "database_host": url_hostname(database_url),
            "message": repr(exc),
            "traceback": traceback.format_exc(),
        }


async def cleanup_identity_users(client: httpx.AsyncClient, pairs: list[PairContext]) -> dict[str, Any]:
    if not CONFIG["CLEANUP_IDENTITY_USERS"]:
        return {"enabled": False, "message": "Identity cleanup disabled."}
    results: list[dict[str, Any]] = []
    users: list[TestUser] = []
    for pair in pairs:
        users.extend([pair.sender, pair.recipient])
    delay = float(CONFIG["CLEANUP_IDENTITY_DELAY_SECONDS"])
    delete_url = api_url(CONFIG["IDENTITY_BASE_URL"], "/api/v1/auth/delete-account")
    for index, user in enumerate(users, start=1):
        try:
            start = time.perf_counter()
            response = await client.request(
                "DELETE",
                delete_url,
                headers={**HTTP_HEADERS, "Authorization": f"Bearer {user.token}"},
                json={
                    "username": user.username,
                    "email": user.email,
                    "contact_number": user.contact_number,
                    "current_password": user.password,
                },
            )
            record_api_call("DELETE", delete_url, response.status_code, (time.perf_counter() - start) * 1000, response.status_code == 200)
            results.append({"username": user.username, "deleted": response.status_code == 200, "status": response.status_code, "body": json_or_text(response)})
        except Exception as exc:
            results.append({"username": user.username, "deleted": False, "error": repr(exc)})
        if delay > 0 and index < len(users):
            await asyncio.sleep(delay)
    return {
        "enabled": True,
        "success": all(item.get("deleted") for item in results),
        "deleted_count": sum(1 for item in results if item.get("deleted")),
        "total_user_count": len(users),
        "failed_samples": [item for item in results if not item.get("deleted")][:20],
    }


def write_reports(report: dict[str, Any]) -> tuple[Path, Path | None]:
    report_dir = Path(str(CONFIG["REPORT_DIR"]))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file_prefix = safe_report_filename_part(
        CONFIG["REPORT_FILE_PREFIX"]
    )
    report_mode = safe_report_filename_part(
        report.get("service_url_mode")
        or report.get("config", {}).get("SERVICE_URL_MODE")
        or CONFIG["SERVICE_URL_MODE"]
    )
    report_file_timestamp = report_timestamp_for_filename()
    report_file_stem = (
        f"{report_file_timestamp}_{report_file_prefix}_{report_mode}_{TEST_RUN_ID}"
    )
    json_path = report_dir / f"{report_file_stem}.json"
    md_path = report_dir / f"{report_file_stem}.md"
    report["report_file_stem"] = report_file_stem
    report["report_file_timestamp"] = report_file_timestamp
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if not CONFIG["WRITE_LEGACY_MARKDOWN"]:
        return json_path, None

    ladder_rows = []
    for item in report.get("benchmark", {}).get("per_level", []):
        lat = item.get("latency_ms", {})
        overall_time = item.get("overall_client_request_time_ms", {})
        main_django_time = item.get("main_django_logic_time_ms", {})
        ladder_rows.append(
            f"| {item.get('concurrency')} | {item.get('total_messages')} | {item.get('success_count')} | {item.get('failure_count')} | "
            f"{item.get('unique_room_id_count')} | {lat.get('avg')} | {lat.get('p95')} | {item.get('total_send_elapsed_ms')} | "
            f"{overall_time.get('total')} | {main_django_time.get('total')} | {main_django_time.get('avg')} | {main_django_time.get('p95')} | "
            f"{item.get('offered_requests_per_second')} | {item.get('successful_messages_per_second')} | {item.get('failed_requests_per_second')} |"
        )
    ladder_table = "\n".join(ladder_rows)
    per_level_server_timing = [
        {
            "concurrency": item.get("concurrency"),
            "server_timing_ms": item.get("server_timing_ms", {}),
        }
        for item in report.get("benchmark", {}).get("per_level", [])
    ]
    per_level_docker_stats = [
        {
            "concurrency": item.get("concurrency"),
            "docker_stats": item.get("docker_stats", {}),
        }
        for item in report.get("benchmark", {}).get("per_level", [])
    ]

    def metric_value(
        stats: dict[str, Any],
        container: str,
        metric: str,
        field: str,
    ) -> Any:
        return (
            stats.get("overall", {})
            .get("containers", {})
            .get(container, {})
            .get(metric, {})
            .get(field)
        )

    def docker_usage_rows(
        *,
        phase_label: str,
        stats: dict[str, Any],
        concurrency: Any = "",
    ) -> list[str]:
        rows = []
        for container in stats.get("container_names", []):
            rows.append(
                f"| {phase_label} | {concurrency} | {container} | "
                f"{metric_value(stats, container, 'cpu_percent', 'avg')} | "
                f"{metric_value(stats, container, 'cpu_percent', 'max')} | "
                f"{metric_value(stats, container, 'mem_usage_mb', 'avg')} | "
                f"{metric_value(stats, container, 'mem_usage_mb', 'max')} | "
                f"{metric_value(stats, container, 'mem_percent', 'avg')} | "
                f"{metric_value(stats, container, 'mem_percent', 'max')} | "
                f"{metric_value(stats, container, 'pids', 'max')} |"
            )
        return rows

    setup_docker_usage_table = "\n".join(
        docker_usage_rows(
            phase_label="setup_pairs",
            stats=report.get("setup", {}).get("docker_stats", {}),
        )
    )
    warmup_docker_usage_table = "\n".join(
        docker_usage_rows(
            phase_label="warmup_create_rooms",
            stats=report.get("warmup", {}).get("docker_stats", {}),
        )
    )

    per_level_docker_usage_rows = []
    for item in report.get("benchmark", {}).get("per_level", []):
        concurrency = item.get("concurrency")
        per_level_docker_usage_rows.extend(
            docker_usage_rows(
                phase_label=f"concurrency_{concurrency}",
                concurrency=concurrency,
                stats=item.get("docker_stats", {}),
            )
        )
    per_level_docker_usage_table = "\n".join(per_level_docker_usage_rows)

    run_mode = report.get("service_url_mode") or report.get("config", {}).get("SERVICE_URL_MODE")
    identity_base_url = report.get("identity_base_url") or report.get("config", {}).get("IDENTITY_BASE_URL")
    messenger_base_url = report.get("messenger_base_url") or report.get("config", {}).get("MESSENGER_BASE_URL")

    md = f"""# Myna Distributed-Pairs Latency Benchmark Report

**Result:** {'PASS' if report.get('passed') else 'FAIL'}  
**Run ID:** `{TEST_RUN_ID}`  
**Service URL mode:** `{run_mode}`  
**Identity base URL:** `{identity_base_url}`  
**Messenger base URL:** `{messenger_base_url}`  
**Traffic mode:** `distributed_pairs`  
**Cleanup success:** `{report.get('cleanup_success')}`  
**Started at:** {report.get('started_at')}  
**Finished at:** {report.get('finished_at')}  

## Configuration

```json
{json.dumps(report.get('config', {}), indent=2, default=str)}
```

## Send Direct Message API Contract

```json
{json.dumps(report.get('send_direct_message_api_contract', {}), indent=2, default=str)}
```

## Service Preflight

```json
{json.dumps(report.get('preflight', {}), indent=2, default=str)}
```

## Runtime Environment

```json
{json.dumps(report.get('runtime_environment', {}), indent=2, default=str)}
```

## Effective Runtime Config

```json
{json.dumps(report.get('effective_runtime_config', {}), indent=2, default=str)}
```

## Database Connection Telemetry

```json
{json.dumps(report.get('database_connection_telemetry', {}), indent=2, default=str)}
```

## Setup

```json
{json.dumps(report.get('setup', {}), indent=2, default=str)}
```

## Warmup

```json
{json.dumps(report.get('warmup', {}), indent=2, default=str)}
```

## Benchmark Ladder

| Concurrency | Requests | Success | Failure | Unique rooms | Avg latency ms | P95 latency ms | Send elapsed ms | Overall req total ms | Main Django total ms | Main Django avg ms | Main Django p95 ms | Offered req/s | Successful msg/s | Failed req/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{ladder_table}

## Benchmark Analysis

```json
{json.dumps(report.get('benchmark', {}).get('analysis', {}), indent=2, default=str)}
```

## Failure Diagnostics

```json
{json.dumps(report.get('failure_diagnostics', {}), indent=2, default=str)}
```

## Overall Summary

```json
{json.dumps(report.get('summary', {}), indent=2, default=str)}
```

## Server Timing Summary

```json
{json.dumps(report.get('summary', {}).get('server_timing_ms', {}), indent=2, default=str)}
```

## Per-Level Server Timing

```json
{json.dumps(per_level_server_timing, indent=2, default=str)}
```

## Docker Resource Usage

### Setup And Warmup Docker Usage

| Phase | Concurrency | Container | Avg CPU % | Max CPU % | Avg RAM MB | Max RAM MB | Avg RAM % | Max RAM % | Max PIDs |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
{setup_docker_usage_table}
{warmup_docker_usage_table}

```json
{json.dumps(report.get('docker_stats', {}), indent=2, default=str)}
```

## Per-Level Docker Resource Usage

| Phase | Concurrency | Container | Avg CPU % | Max CPU % | Avg RAM MB | Max RAM MB | Avg RAM % | Max RAM % | Max PIDs |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
{per_level_docker_usage_table}

```json
{json.dumps(per_level_docker_stats, indent=2, default=str)}
```

## API Timings

```json
{json.dumps(report.get('api_timings', {}).get('by_endpoint', {}), indent=2, default=str)}
```

## Cleanup

```json
{json.dumps(report.get('cleanup', {}), indent=2, default=str)}
```

## Failure Samples

```json
{json.dumps(report.get('summary', {}).get('failed_samples', []), indent=2, default=str)}
```
"""
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path


async def run() -> int:
    started_at = utc_now_iso()
    levels = parse_int_list(str(CONFIG["BENCHMARK_LEVELS"]))
    pair_count = int(CONFIG["DISTRIBUTED_PAIR_COUNT"] or max(levels))
    if pair_count < max(levels):
        raise RuntimeError(f"DISTRIBUTED_PAIR_COUNT={pair_count} is less than max benchmark level {max(levels)}.")

    report: dict[str, Any] = {
        "run_id": TEST_RUN_ID,
        "started_at": started_at,
        "service_url_mode": CONFIG["SERVICE_URL_MODE"],
        "identity_base_url": CONFIG["IDENTITY_BASE_URL"],
        "messenger_base_url": CONFIG["MESSENGER_BASE_URL"],
        "identity_base_url_source": CONFIG["IDENTITY_BASE_URL_SOURCE"],
        "messenger_base_url_source": CONFIG["MESSENGER_BASE_URL_SOURCE"],
        "traffic_mode": "distributed_pairs",
        "send_direct_message_api_contract": send_direct_message_api_contract(),
        "config": CONFIG,
        "effective_runtime_config": {
            "benchmark_http": {
                "MYNA_HTTP_MAX_CONNECTIONS": CONFIG["HTTP_MAX_CONNECTIONS"],
                "MYNA_HTTP_MAX_KEEPALIVE_CONNECTIONS": CONFIG["HTTP_MAX_KEEPALIVE_CONNECTIONS"],
                "MYNA_HTTP_KEEPALIVE_EXPIRY_SECONDS": CONFIG["HTTP_KEEPALIVE_EXPIRY_SECONDS"],
                "MYNA_HTTP_POOL_TIMEOUT_SECONDS": CONFIG["HTTP_POOL_TIMEOUT_SECONDS"],
                "MYNA_BENCHMARK_COOLDOWN_SECONDS": CONFIG["BENCHMARK_COOLDOWN_SECONDS"],
                "MYNA_CONNECTION_WARMUP_CONCURRENCY": CONFIG["CONNECTION_WARMUP_CONCURRENCY"],
                "MYNA_ACTIVE_CLIENT_SETTLE_SECONDS": CONFIG["ACTIVE_CLIENT_SETTLE_SECONDS"],
                "ACTIVE_CLIENT_MODEL": "one_persistent_async_client_per_pair",
                "ACTIVE_CLIENT_POOL_MAX_CONNECTIONS": 1,
                "ACTIVE_CLIENT_POOL_MAX_KEEPALIVE_CONNECTIONS": 1,
            }
        },
        "runtime_environment": collect_runtime_environment_snapshot(),
        "passed": False,
    }
    pairs: list[PairContext] = []
    all_records: list[SentMessageRecord] = []
    docker_stats_sampler = DockerStatsSampler()
    report["httpx_client_lifecycle"] = {
        "setup_client": "preflight, pair setup, and room-creation warmup",
        "measured_clients": (
            "one persistent AsyncClient per sender/pair; each client owns an "
            "independent one-connection pool and is reused across levels"
        ),
        "connection_mode": "dedicated_persistent_client_per_active_user",
        "measured_start_model": "coordinated_asyncio_event_barrier",
        "per_level_connection_refresh": (
            "unmeasured health request on each selected client immediately before "
            "the measured send level"
        ),
        "cleanup_client": "identity cleanup only",
    }

    try:
        async with make_benchmark_http_client() as setup_client:
            await add_mysql_telemetry(report, "initial_pre_benchmark")
            report["preflight"] = await preflight_service_urls(setup_client)
            await docker_stats_sampler.start("setup_pairs")
            try:
                pairs = await setup_pairs(setup_client, pair_count)
            finally:
                await docker_stats_sampler.stop()
            report["setup"] = {
                "pair_count": len(pairs),
                "sender_user_ids_sample": [p.sender.user_id for p in pairs[:10]],
                "recipient_user_ids_sample": [p.recipient.user_id for p in pairs[:10]],
                "failure_diagnostics": summarize_setup_step_records(pair_count, len(pairs)),
                "docker_stats": docker_stats_sampler.phase_summary("setup_pairs"),
            }

            pairs_by_index = {pair.index: pair for pair in pairs}
            report["pre_warmup_cache_invalidation"] = await asyncio.to_thread(
                invalidate_messenger_user_caches,
                pairs,
            )
            if not report["pre_warmup_cache_invalidation"].get("success", False):
                raise RuntimeError(
                    "Pre-warmup Messenger cache invalidation failed: "
                    f"{report['pre_warmup_cache_invalidation']}"
                )
            sequence = 0

            if CONFIG["WARMUP_ALL_PAIRS"]:
                set_api_phase("warmup_create_rooms", None)
                log_progress(f"Warmup enabled: creating {len(pairs)} direct rooms with one first message per pair...")
                warmup_phase = "warmup_create_rooms"
                warmup_records = []
                for pair in pairs:
                    sequence += 1
                    warmup_records.append(build_send_payload_for_pair(
                        pair=pair,
                        sequence=sequence,
                        benchmark_concurrency=None,
                        force_contact_id=True,
                    ))
                # Keep warmup concurrency modest; it is not measured as benchmark latency.
                await docker_stats_sampler.start(warmup_phase)
                try:
                    await send_concurrently(setup_client, records=warmup_records, concurrency=min(10, len(warmup_records)))
                finally:
                    await docker_stats_sampler.stop()
                apply_room_ids_to_pairs(warmup_records, pairs_by_index)
                warmup_summary = summarize_records(warmup_records, concurrency="warmup")
                warmup_summary["docker_stats"] = docker_stats_sampler.phase_summary(warmup_phase)
                report["warmup"] = warmup_summary
                log_progress(f"Warmup done: success={warmup_summary['success_count']}, failure={warmup_summary['failure_count']}, rooms={warmup_summary['unique_room_id_count']}")
                if warmup_summary["failure_count"] > 0:
                    raise RuntimeError("Warmup failed; direct rooms were not created for all pairs.")

            per_level: list[dict[str, Any]] = []
            print_benchmark_level_table_header()

            # Measured load model: one persistent HTTPX client per sender/pair.
            # A shared AsyncClient owns one shared connection pool. Under high load,
            # benchmark-side pool acquisition can dominate first_event_delay and make
            # the load generator look like server latency. Dedicated clients model
            # independent active users and eliminate that shared-pool queue.
            async with AsyncExitStack() as measured_client_stack:
                clients_by_pair_index: dict[int, httpx.AsyncClient] = {}
                for pair in pairs:
                    active_limits = httpx.Limits(
                        max_connections=1,
                        max_keepalive_connections=1,
                        keepalive_expiry=float(CONFIG["HTTP_KEEPALIVE_EXPIRY_SECONDS"]),
                    )
                    active_timeout = httpx.Timeout(
                        connect=10.0,
                        read=float(CONFIG["REQUEST_TIMEOUT_SECONDS"]),
                        write=10.0,
                        pool=float(CONFIG["HTTP_POOL_TIMEOUT_SECONDS"]),
                    )
                    active_client = httpx.AsyncClient(
                        timeout=active_timeout,
                        limits=active_limits,
                        follow_redirects=False,
                        event_hooks={
                            "request": [record_httpx_request_hook],
                            "response": [record_httpx_response_hook],
                        },
                    )
                    clients_by_pair_index[pair.index] = await measured_client_stack.enter_async_context(
                        active_client
                    )

                initial_warmup_count = min(
                    max(levels),
                    max(1, int(CONFIG["CONNECTION_WARMUP_CONCURRENCY"] or max(levels))),
                )
                initial_warmup_pairs = pairs[:initial_warmup_count]
                await add_mysql_telemetry(report, "before_connection_warmup")
                initial_connection_warmup = await warm_active_user_clients(
                    clients_by_pair_index,
                    pairs=initial_warmup_pairs,
                    phase="initial_active_user_connection_warmup",
                )
                initial_connection_warmup["configured_initial_warmup_concurrency"] = int(
                    CONFIG["CONNECTION_WARMUP_CONCURRENCY"]
                )
                initial_connection_warmup["per_level_refreshes_all_selected_clients"] = True
                await add_mysql_telemetry(report, "after_connection_warmup")
                report["connection_warmup"] = initial_connection_warmup

                for level in levels:
                    selected_pairs = pairs[:level]
                    prelevel_warmup = await warm_active_user_clients(
                        clients_by_pair_index,
                        pairs=selected_pairs,
                        phase=f"prelevel_active_user_connection_warmup_{level}",
                    )

                    level_records = []
                    for pair in selected_pairs:
                        sequence += 1
                        level_records.append(build_send_payload_for_pair(
                            pair=pair,
                            sequence=sequence,
                            benchmark_concurrency=level,
                            force_contact_id=not bool(pair.room_id),
                        ))
                    set_api_phase(f"send_concurrency_{level}", level)
                    assign_benchmark_headers(
                        level_records,
                        concurrency=level,
                        phase=f"send_concurrency_{level}",
                    )
                    log_progress(
                        f"Level concurrency={level}: releasing {len(level_records)} "
                        "independent active-user clients together..."
                    )
                    level_phase = f"concurrency_{level}"
                    await add_mysql_telemetry(report, f"before_concurrency_{level}")
                    await docker_stats_sampler.start(level_phase)
                    launch_summary: dict[str, Any] = {}
                    try:
                        launch_summary = await send_active_users_concurrently(
                            clients_by_pair_index,
                            records=level_records,
                            concurrency=level,
                        )
                    finally:
                        await docker_stats_sampler.stop()
                    elapsed_ms = float(launch_summary.get("elapsed_ms") or 0.0)
                    apply_room_ids_to_pairs(level_records, pairs_by_index)
                    level_summary = summarize_records(level_records, concurrency=level)
                    level_summary["httpx_connection_mode"] = "dedicated_persistent_client_per_active_user"
                    level_summary["httpx_client_reused_across_levels"] = True
                    level_summary["active_user_client_count"] = level
                    level_summary["active_user_client_pool_max_connections"] = 1
                    level_summary["active_user_client_pool_max_keepalive_connections"] = 1
                    level_summary["load_generator_model"] = "one_async_client_per_pair_with_start_barrier"
                    level_summary["load_generator_launch"] = launch_summary
                    level_summary["prelevel_connection_warmup"] = prelevel_warmup
                    level_summary["total_send_elapsed_ms"] = round(elapsed_ms, 2)
                    add_throughput_metrics(level_summary, elapsed_ms=elapsed_ms)
                    level_summary["docker_stats"] = docker_stats_sampler.phase_summary(level_phase)
                    await add_mysql_telemetry(report, f"after_concurrency_{level}")
                    per_level.append(level_summary)
                    all_records.extend(level_records)
                    print_benchmark_level_table_row(level_summary)
                    connection_counts = level_summary.get("httpx_trace_connection_counts", {})
                    dispatch_skew = level_summary.get("load_generator_dispatch_skew_ms", {})
                    log_progress(
                        f"Level concurrency={level} done: success={level_summary['success_count']}, "
                        f"failure={level_summary['failure_count']}, rooms={level_summary['unique_room_id_count']}, "
                        f"avg_ms={level_summary['latency_ms'].get('avg')}, p95_ms={level_summary['latency_ms'].get('p95')}, "
                        f"dispatch_skew_p95_ms={dispatch_skew.get('p95')}, "
                        f"first_event_delay_avg_ms={(level_summary.get('httpx_trace_ms', {}).get('first_event_delay', {}) or {}).get('avg')}, "
                        f"new_tcp={connection_counts.get('new_tcp_connection')}, "
                        f"no_connect_event={connection_counts.get('no_connect_tcp_event')}, "
                        f"no_connect_pct={connection_counts.get('no_connect_tcp_event_percent')}, "
                        f"msg_per_sec={level_summary.get('messages_per_second')}"
                    )
                    if CONFIG["STOP_ON_FIRST_FAILED_LEVEL"] and level_summary.get("failure_count", 0) > 0:
                        break
                    cooldown = float(CONFIG["BENCHMARK_COOLDOWN_SECONDS"])
                    if cooldown > 0 and level != levels[-1]:
                        await asyncio.sleep(cooldown)

            summary = summarize_records(all_records, concurrency="distributed_ladder")
            summary["benchmark_level_count"] = len(per_level)
            summary["total_benchmark_messages"] = len(all_records)
            report["summary"] = summary
            report["docker_stats"] = docker_stats_sampler.summary()
            report["benchmark"] = {
                "enabled": True,
                "levels_requested": levels,
                "pair_count": pair_count,
                "warmup_all_pairs": bool(CONFIG["WARMUP_ALL_PAIRS"]),
                "connection_mode": "dedicated_persistent_client_per_active_user",
                "persistent_httpx_client_reused_across_levels": True,
                "active_user_client_model": "one_async_client_per_pair_with_one_connection_pool_slot",
                "coordinated_start_barrier": True,
                "per_level_connection_refresh": True,
                "per_level": per_level,
                "analysis": analyze_benchmark_levels(per_level),
            }
            expected_total = len(all_records)
            report["passed"] = (
                summary.get("success_count") == expected_total
                and summary.get("failure_count") == 0
                and summary.get("unique_message_id_count") == expected_total
                and summary.get("duplicate_message_id_count") == 0
                and summary.get("unique_room_id_count") >= max(levels)
            )

    except Exception as exc:
        await docker_stats_sampler.stop()
        report["fatal_error"] = repr(exc)
        report["traceback"] = traceback.format_exc()
        report.setdefault(
            "setup",
            {
                "pair_count": len(pairs),
                "failure_diagnostics": summarize_setup_step_records(pair_count, len(pairs)),
                "docker_stats": docker_stats_sampler.phase_summary("setup_pairs"),
            },
        )
        report.setdefault("summary", summarize_records(all_records, concurrency="distributed_ladder"))
        report["docker_stats"] = docker_stats_sampler.summary()
    finally:
        await docker_stats_sampler.stop()
        set_api_phase("cleanup")
        log_progress("Starting cleanup...")
        await add_mysql_telemetry(report, "before_cleanup")
        messenger_cleanup = await asyncio.to_thread(cleanup_messenger_with_django, pairs)
        async with make_benchmark_http_client() as cleanup_client:
            identity_cleanup = await cleanup_identity_users(cleanup_client, pairs)
        report["cleanup"] = {"messenger": messenger_cleanup, "identity": identity_cleanup}
        report["cleanup_success"] = bool(
            messenger_cleanup.get("success", True)
            and identity_cleanup.get("success", True)
        )
        await add_mysql_telemetry(report, "after_cleanup")
        report["api_timings"] = summarize_api_calls(API_CALL_RECORDS)
        report["finished_at"] = utc_now_iso()
        report["failure_diagnostics"] = collect_report_failure_diagnostics(report)
        json_path, md_path = write_reports(report)
        if md_path is not None:
            log_progress(f"Reports written: {json_path} and {md_path}")
        else:
            log_progress(f"Primary JSON report written: {json_path}")
        print(json.dumps({
            "passed": report.get("passed"),
            "run_id": TEST_RUN_ID,
            "service_url_mode": report.get("service_url_mode"),
            "identity_base_url": report.get("identity_base_url"),
            "messenger_base_url": report.get("messenger_base_url"),
            "json_report": str(json_path),
            "markdown_report": str(md_path) if md_path is not None else None,
            "summary": report.get("summary"),
            "benchmark_analysis": (report.get("benchmark") or {}).get("analysis"),
            "failure_diagnostics": report.get("failure_diagnostics"),
            "runtime_environment": report.get("runtime_environment"),
            "api_timings_by_endpoint": (report.get("api_timings") or {}).get("by_endpoint"),
            "cleanup": report.get("cleanup"),
            "cleanup_success": report.get("cleanup_success"),
            "fatal_error": report.get("fatal_error"),
        }, indent=2, default=str))

    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
