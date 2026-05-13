#!/usr/bin/env sh
# Docker entrypoint: run Alembic migrations, then start the application.
# Using /bin/sh (POSIX) for maximum compatibility with slim Python images.

set -e

echo "[entrypoint] Running database migrations..."
python -m alembic upgrade head

echo "[entrypoint] Starting TaleWeaver backend..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
