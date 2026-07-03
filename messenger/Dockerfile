FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    MESSENGER_DOCKER=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system appuser \
    && useradd --system \
        --gid appuser \
        --create-home \
        appuser

COPY requirements.txt requirements-docker.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-docker.txt

COPY --chown=appuser:appuser apps ./apps
COPY --chown=appuser:appuser messenger_config ./messenger_config
COPY --chown=appuser:appuser manage.py docker_entrypoint.py ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; port=os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health/', timeout=5)"]

ENTRYPOINT ["python", "docker_entrypoint.py"]

CMD ["sh", "-c", "ACCESS_LOGFILE=/dev/null; if [ \"${GUNICORN_ACCESS_LOG:-1}\" = \"1\" ]; then ACCESS_LOGFILE=-; fi; exec gunicorn messenger_config.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-5} --backlog ${GUNICORN_BACKLOG:-2048} --timeout ${GUNICORN_TIMEOUT:-60} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-30} --keep-alive ${GUNICORN_KEEP_ALIVE:-5} --access-logfile \"$ACCESS_LOGFILE\" --error-logfile -"]
