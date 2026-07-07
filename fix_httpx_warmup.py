from pathlib import Path
import re


BENCHMARK_FILE = Path(
    "messenger/api_tests/full_api_flow/"
    "myna_distributed_pairs_latency_benchmark_test.py"
)

ENV_FILES = (
    Path(".env.benchmark.runner.docker-network.full.local"),
    Path(".env.benchmark.runner.docker-network.local"),
)


def replace_once(text: str, old: str, new: str, name: str) -> str:
    if old not in text:
        raise RuntimeError(
            f"\nPATCH FAILED: {name}\n"
            "Expected old code was not found.\n"
            "No benchmark file was written."
        )

    return text.replace(old, new, 1)


def patch_benchmark() -> None:
    if not BENCHMARK_FILE.exists():
        raise FileNotFoundError(
            f"Benchmark file not found: {BENCHMARK_FILE}"
        )

    original = BENCHMARK_FILE.read_text(encoding="utf-8")
    text = original

    text = replace_once(
        text,
        '''    log_progress(
        f"Connection warmup done: success={summary['success_count']}, failure={summary['failure_count']}, "
        f"cooldown={CONFIG['BENCHMARK_COOLDOWN_SECONDS']}s"
    )
    if float(CONFIG["BENCHMARK_COOLDOWN_SECONDS"]) > 0:
        await asyncio.sleep(float(CONFIG["BENCHMARK_COOLDOWN_SECONDS"]))
    return sequence, summary
''',
        '''    log_progress(
        f"Connection warmup done: success={summary['success_count']}, "
        f"failure={summary['failure_count']}; "
        "reusing the same HTTPX client pool immediately"
    )
    return sequence, summary
''',
        "remove post-warmup cooldown",
    )

    text = replace_once(
        text,
        '''    report["httpx_client_lifecycle"] = {
        "setup_client": "preflight, pair setup, and room-creation warmup",
        "connection_warmup_client": "optional unmeasured connection warmup only",
        "measured_clients": "fresh AsyncClient per measured concurrency level",
        "cleanup_client": "identity cleanup only",
    }
''',
        '''    report["httpx_client_lifecycle"] = {
        "setup_and_benchmark_client": (
            "single shared AsyncClient for preflight, setup, "
            "connection warmup, and measured concurrency levels "
            "so the warmed HTTP connection pool is reused"
        ),
        "cleanup_client": "identity cleanup only",
    }
''',
        "update HTTPX client lifecycle report",
    )

    text = replace_once(
        text,
        '''            await add_mysql_telemetry(report, "before_connection_warmup")
            async with make_benchmark_http_client() as connection_warmup_client:
                sequence, connection_warmup_summary = await run_connection_warmup(
                    connection_warmup_client,
                    pairs=pairs,
                    pairs_by_index=pairs_by_index,
                    sequence_start=sequence,
                    max_level=max(levels),
                )
''',
        '''            await add_mysql_telemetry(report, "before_connection_warmup")
            sequence, connection_warmup_summary = await run_connection_warmup(
                setup_client,
                pairs=pairs,
                pairs_by_index=pairs_by_index,
                sequence_start=sequence,
                max_level=max(levels),
            )
''',
        "reuse setup client for connection warmup",
    )

    text = replace_once(
        text,
        '''                try:
                    async with make_benchmark_http_client() as measured_client:
                        await send_concurrently(measured_client, records=level_records, concurrency=level)
                finally:
''',
        '''                try:
                    await send_concurrently(
                        setup_client,
                        records=level_records,
                        concurrency=level,
                    )
                finally:
''',
        "reuse warmed client for measured requests",
    )

    BENCHMARK_FILE.write_text(text, encoding="utf-8")

    print(f"Patched benchmark: {BENCHMARK_FILE}")


def patch_environment() -> None:
    found = False

    for env_file in ENV_FILES:
        if not env_file.exists():
            continue

        found = True
        text = env_file.read_text(encoding="utf-8")

        updated, count = re.subn(
            r"^MYNA_CONNECTION_WARMUP_CONCURRENCY=.*$",
            "MYNA_CONNECTION_WARMUP_CONCURRENCY=300",
            text,
            count=1,
            flags=re.MULTILINE,
        )

        if count == 0:
            if updated and not updated.endswith("\n"):
                updated += "\n"

            updated += "MYNA_CONNECTION_WARMUP_CONCURRENCY=300\n"

        env_file.write_text(updated, encoding="utf-8")

        print(
            f"Updated warmup concurrency: {env_file}"
        )

    if not found:
        print(
            "WARNING: benchmark env files were not found. "
            "Benchmark code was still patched."
        )


def main() -> None:
    patch_benchmark()
    patch_environment()

    print()
    print("HTTPX WARMUP FIX APPLIED SUCCESSFULLY")
    print(
        "Warmup and C300 measurement now reuse "
        "the same HTTPX AsyncClient pool."
    )


if __name__ == "__main__":
    main()