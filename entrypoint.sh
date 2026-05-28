#!/usr/bin/env sh
# Docker entrypoint: run Alembic migrations, then start the application.
# Using /bin/sh (POSIX) for maximum compatibility with slim Python images.

set -e

echo "[entrypoint] Running database migrations..."
python -m alembic upgrade head

WORKERS="${WEB_CONCURRENCY:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-30}"

echo "[entrypoint] Starting TaleWeaver backend with Gunicorn (${WORKERS} workers)..."
exec gunicorn backend.main:app \
	--worker-class uvicorn.workers.UvicornWorker \
	--workers "${WORKERS}" \
	--bind 0.0.0.0:8000 \
	--timeout "${TIMEOUT}" \
	--graceful-timeout "${GRACEFUL_TIMEOUT}"
