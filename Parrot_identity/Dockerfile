FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    GUNICORN_CMD_ARGS="--bind=0.0.0.0:5000 --workers=2 --threads=4 --timeout=60 --access-logfile=- --error-logfile=-"

WORKDIR /app

RUN groupadd --system parrot \
    && useradd --system --gid parrot --create-home parrot

COPY requirements.txt requirements-docker.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-docker.txt

COPY --chown=parrot:parrot app ./app
COPY --chown=parrot:parrot migrations ./migrations
COPY --chown=parrot:parrot parrot_identity.py docker_entrypoint.py ./

USER parrot

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/v1/health', timeout=5)"]

ENTRYPOINT ["python", "docker_entrypoint.py"]
CMD ["gunicorn", "parrot_identity:app"]
