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
    && rm -rf /var/lib/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY version.json .

# Copy adventures (for automatic import)
COPY adventures/ ./adventures/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend_dist

# Expose backend port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=data

# Start application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
