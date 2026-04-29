#!/bin/bash

# TaleWeaver Docker Setup Script
# This script builds and starts the TaleWeaver container.

# Navigate to project root
cd "$(dirname "$0")/.."

echo "--- TaleWeaver Docker Setup ---"

# Check for .env file
if [ ! -f .env ]; then
    echo "[!] .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "[i] Please edit the .env file and set your ENCRYPTION_KEY and API keys."
fi

# Create data directory if it doesn't exist to ensure correct permissions
mkdir -p data

# Build and start
echo "[*] Building and starting container..."
docker compose up -d --build

# Get port from .env or default
PORT=$(grep BACKEND_PORT .env | cut -d '=' -f2)
PORT=${PORT:-8000}

echo "--------------------------------"
echo "[+] TaleWeaver is now running!"
echo "[+] Access the UI at: http://localhost:$PORT"
echo "[+] Logs: docker compose logs -f"
echo "--------------------------------"
