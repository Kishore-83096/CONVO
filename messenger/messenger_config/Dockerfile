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
    && useradd --system --gid appuser --create-home appuser

COPY requirements.txt requirements-docker.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-docker.txt

COPY --chown=appuser:appuser apps ./apps
COPY --chown=appuser:appuser messenger_config ./messenger_config
COPY --chown=appuser:appuser manage.py docker_entrypoint.py docker_start_messenger.sh ./
RUN chmod +x docker_start_messenger.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["python", "docker_entrypoint.py"]
CMD ["sh", "docker_start_messenger.sh"]
