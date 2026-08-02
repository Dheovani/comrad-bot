FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIRECTORY=/app/data \
    SOUNDS_DIRECTORY=/app/data/sounds \
    DATABASE_URL=sqlite+aiosqlite:////app/data/comradbot.db \
    HEALTHCHECK_HEARTBEAT_FILE=/app/data/.heartbeat \
    ALEMBIC_CONFIG_FILE=/app/alembic.ini \
    ALEMBIC_DIRECTORY=/app/alembic

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 comradbot \
    && useradd --system --uid 10001 --gid comradbot --home-dir /app --shell /usr/sbin/nologin comradbot

WORKDIR /app

COPY pyproject.toml README.md LICENSE alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN python -m pip install --no-cache-dir . \
    && mkdir -p /app/data \
    && chown -R comradbot:comradbot /app/data

USER comradbot

VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD ["python", "-m", "comradbot.healthcheck"]

CMD ["python", "-m", "comradbot"]
