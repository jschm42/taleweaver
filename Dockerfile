# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Final image
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/lists/*

# Install poetry
ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry>=2.0.0"

# Install python dependencies
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-root --without dev


# Copy backend code
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY version.json .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Install project package
RUN poetry install --without dev

# Copy adventures (for automatic import)
COPY adventures/ ./adventures/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend_dist

# Expose backend port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=data

# Run migrations then start the application
ENTRYPOINT ["./entrypoint.sh"]
