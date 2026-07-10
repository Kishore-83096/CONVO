#!/bin/sh
set -eu

env_value() {
    name="$1"
    default="$2"
    eval "value=\${$name:-}"
    if [ -n "$value" ]; then
        printf '%s' "$value"
    else
        printf '%s' "$default"
    fi
}

access_logfile() {
    if [ -n "${GUNICORN_ACCESS_LOG_FILE:-}" ]; then
        printf '%s' "$GUNICORN_ACCESS_LOG_FILE"
        return
    fi
    if [ -n "${GUNICORN_ACCESS_LOGFILE:-}" ]; then
        printf '%s' "$GUNICORN_ACCESS_LOGFILE"
        return
    fi
    if [ "$(env_value GUNICORN_ACCESS_LOG 0)" = "1" ]; then
        printf '%s' "-"
    else
        printf '%s' "/dev/null"
    fi
}

role="$(env_value MESSENGER_PROCESS_ROLE http)"
port="$(env_value PORT 8000)"

export ASGI_THREADS="$(env_value ASGI_THREADS 12)"

case "$role" in
    http)
        http_mode="$(env_value MESSENGER_HTTP_SERVER_MODE wsgi)"
        if [ "$http_mode" = "wsgi" ]; then
            benchmark_profile_enabled="$(env_value MYNA_PROFILE_DIRECT_SEND false)"
            case "$benchmark_profile_enabled" in
                1|true|TRUE|yes|YES|on|ON)
                    default_wsgi_worker="messenger_config.benchmark_gthread_worker.BenchmarkThreadWorker"
                    ;;
                *)
                    default_wsgi_worker="gthread"
                    ;;
            esac
            wsgi_worker_class="$(env_value GUNICORN_WORKER_CLASS "$default_wsgi_worker")"
            echo "Starting Messenger HTTP WSGI role on 0.0.0.0:${port} with WEB_CONCURRENCY=$(env_value WEB_CONCURRENCY 4), GUNICORN_THREADS=$(env_value GUNICORN_THREADS 8), GUNICORN_WORKER_CLASS=${wsgi_worker_class}, GUNICORN_WORKER_CONNECTIONS=$(env_value GUNICORN_WORKER_CONNECTIONS 24), GUNICORN_BACKLOG=$(env_value GUNICORN_BACKLOG 4096), DB_CONN_MAX_AGE=${DB_CONN_MAX_AGE:-role-default}, DB_CONN_HEALTH_CHECKS=$(env_value DB_CONN_HEALTH_CHECKS true)" >&2
            set -- \
                gunicorn messenger_config.wsgi:application \
                --worker-class "$wsgi_worker_class" \
                --threads "$(env_value GUNICORN_THREADS 12)" \
                --worker-connections "$(env_value GUNICORN_WORKER_CONNECTIONS 30)" \
                --bind "0.0.0.0:${port}" \
                --workers "$(env_value WEB_CONCURRENCY 6)" \
                --backlog "$(env_value GUNICORN_BACKLOG 4096)" \
                --timeout "$(env_value GUNICORN_TIMEOUT 60)" \
                --graceful-timeout "$(env_value GUNICORN_GRACEFUL_TIMEOUT 30)" \
                --keep-alive "$(env_value GUNICORN_KEEP_ALIVE 5)" \
                --max-requests "$(env_value GUNICORN_MAX_REQUESTS 0)" \
                --max-requests-jitter "$(env_value GUNICORN_MAX_REQUESTS_JITTER 0)" \
                --access-logfile "$(access_logfile)" \
                --error-logfile -
            if [ -n "${GUNICORN_ACCESS_LOG_FORMAT:-}" ]; then
                set -- "$@" --access-logformat "$GUNICORN_ACCESS_LOG_FORMAT"
            fi
            exec "$@"
        fi
        if [ "$http_mode" != "asgi" ]; then
            echo "Invalid MESSENGER_HTTP_SERVER_MODE: ${http_mode}. Expected one of: asgi, wsgi." >&2
            exit 2
        fi
        echo "Starting Messenger HTTP ASGI role on 0.0.0.0:${port} with WEB_CONCURRENCY=$(env_value WEB_CONCURRENCY 4), ASGI_THREADS=${ASGI_THREADS}, GUNICORN_BACKLOG=$(env_value GUNICORN_BACKLOG 4096), DB_CONN_MAX_AGE=${DB_CONN_MAX_AGE:-role-default}, DB_CONN_HEALTH_CHECKS=$(env_value DB_CONN_HEALTH_CHECKS true)" >&2
        set -- \
            gunicorn messenger_config.asgi:application \
            -k uvicorn_worker.UvicornWorker \
            --bind "0.0.0.0:${port}" \
            --workers "$(env_value WEB_CONCURRENCY 6)" \
            --backlog "$(env_value GUNICORN_BACKLOG 4096)" \
            --timeout "$(env_value GUNICORN_TIMEOUT 60)" \
            --graceful-timeout "$(env_value GUNICORN_GRACEFUL_TIMEOUT 30)" \
            --keep-alive "$(env_value GUNICORN_KEEP_ALIVE 5)" \
            --max-requests "$(env_value GUNICORN_MAX_REQUESTS 0)" \
            --max-requests-jitter "$(env_value GUNICORN_MAX_REQUESTS_JITTER 0)" \
            --access-logfile "$(access_logfile)" \
            --error-logfile -
        if [ -n "${GUNICORN_ACCESS_LOG_FORMAT:-}" ]; then
            set -- "$@" --access-logformat "$GUNICORN_ACCESS_LOG_FORMAT"
        fi
        exec "$@"
        ;;
    websocket)
        port="$(env_value PORT 8001)"
        echo "Starting Messenger WebSocket ASGI role on 0.0.0.0:${port} with ASGI_THREADS=${ASGI_THREADS}, DB_CONN_MAX_AGE=${DB_CONN_MAX_AGE:-role-default}, DB_CONN_HEALTH_CHECKS=$(env_value DB_CONN_HEALTH_CHECKS true)" >&2
        exec daphne -b 0.0.0.0 -p "$port" messenger_config.asgi:application
        ;;
    outbox)
        echo "Starting Messenger realtime outbox worker with REALTIME_OUTBOX_BATCH_SIZE=$(env_value REALTIME_OUTBOX_BATCH_SIZE 100), REALTIME_OUTBOX_POLL_INTERVAL_SECONDS=$(env_value REALTIME_OUTBOX_POLL_INTERVAL_SECONDS 1), DB_CONN_MAX_AGE=${DB_CONN_MAX_AGE:-role-default}, DB_CONN_HEALTH_CHECKS=$(env_value DB_CONN_HEALTH_CHECKS true)" >&2
        exec python manage.py run_realtime_outbox_worker
        ;;
    *)
        echo "Invalid MESSENGER_PROCESS_ROLE: ${role}. Expected one of: http, websocket, outbox." >&2
        exit 2
        ;;
esac
