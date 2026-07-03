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
    if [ "$(env_value GUNICORN_ACCESS_LOG 1)" = "1" ]; then
        printf '%s' "-"
    else
        printf '%s' "/dev/null"
    fi
}

role="$(env_value MESSENGER_PROCESS_ROLE http)"
port="$(env_value PORT 8000)"

export ASGI_THREADS="$(env_value ASGI_THREADS 8)"

case "$role" in
    http)
        http_mode="$(env_value MESSENGER_HTTP_SERVER_MODE asgi)"
        if [ "$http_mode" = "wsgi" ]; then
            echo "Starting Messenger HTTP legacy WSGI mode on 0.0.0.0:${port} with WEB_CONCURRENCY=$(env_value WEB_CONCURRENCY 5), GUNICORN_THREADS=$(env_value GUNICORN_THREADS 8), GUNICORN_BACKLOG=$(env_value GUNICORN_BACKLOG 4096)" >&2
            set -- \
                gunicorn messenger_config.wsgi:application \
                --worker-class gthread \
                --threads "$(env_value GUNICORN_THREADS 8)" \
                --bind "0.0.0.0:${port}" \
                --workers "$(env_value WEB_CONCURRENCY 5)" \
                --backlog "$(env_value GUNICORN_BACKLOG 4096)" \
                --timeout "$(env_value GUNICORN_TIMEOUT 60)" \
                --graceful-timeout "$(env_value GUNICORN_GRACEFUL_TIMEOUT 30)" \
                --keep-alive "$(env_value GUNICORN_KEEP_ALIVE 5)" \
                --max-requests "$(env_value GUNICORN_MAX_REQUESTS 1000)" \
                --max-requests-jitter "$(env_value GUNICORN_MAX_REQUESTS_JITTER 100)" \
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
        echo "Starting Messenger HTTP ASGI role on 0.0.0.0:${port} with WEB_CONCURRENCY=$(env_value WEB_CONCURRENCY 5), ASGI_THREADS=${ASGI_THREADS}, GUNICORN_BACKLOG=$(env_value GUNICORN_BACKLOG 4096)" >&2
        set -- \
            gunicorn messenger_config.asgi:application \
            -k uvicorn_worker.UvicornWorker \
            --bind "0.0.0.0:${port}" \
            --workers "$(env_value WEB_CONCURRENCY 5)" \
            --backlog "$(env_value GUNICORN_BACKLOG 4096)" \
            --timeout "$(env_value GUNICORN_TIMEOUT 60)" \
            --graceful-timeout "$(env_value GUNICORN_GRACEFUL_TIMEOUT 30)" \
            --keep-alive "$(env_value GUNICORN_KEEP_ALIVE 5)" \
            --max-requests "$(env_value GUNICORN_MAX_REQUESTS 1000)" \
            --max-requests-jitter "$(env_value GUNICORN_MAX_REQUESTS_JITTER 100)" \
            --access-logfile "$(access_logfile)" \
            --error-logfile -
        if [ -n "${GUNICORN_ACCESS_LOG_FORMAT:-}" ]; then
            set -- "$@" --access-logformat "$GUNICORN_ACCESS_LOG_FORMAT"
        fi
        exec "$@"
        ;;
    websocket)
        port="$(env_value PORT 8001)"
        echo "Starting Messenger WebSocket ASGI role on 0.0.0.0:${port} with ASGI_THREADS=${ASGI_THREADS}" >&2
        exec daphne -b 0.0.0.0 -p "$port" messenger_config.asgi:application
        ;;
    *)
        echo "Invalid MESSENGER_PROCESS_ROLE: ${role}. Expected one of: http, websocket." >&2
        exit 2
        ;;
esac
