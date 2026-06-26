FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_CONCURRENCY=1 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=60

WORKDIR /app

RUN groupadd --system appuser \
    && useradd --system \
        --gid appuser \
        --create-home \
        appuser

COPY requirements.txt requirements-docker.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-docker.txt

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser identity_service.py docker_entrypoint.py ./

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; port=os.environ.get('PORT', '5000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=5)"]

ENTRYPOINT ["python", "docker_entrypoint.py"]

CMD ["sh", "-c", "exec gunicorn \
    --bind 0.0.0.0:${PORT:-5000} \
    --worker-class gthread \
    --workers ${WEB_CONCURRENCY:-1} \
    --threads ${GUNICORN_THREADS:-4} \
    --timeout ${GUNICORN_TIMEOUT:-60} \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    identity_service:app"]
