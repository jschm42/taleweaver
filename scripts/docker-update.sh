#!/bin/bash

# TaleWeaver Docker Update Script
# This script pulls the latest changes and recreates the container.

# Navigate to project root
cd "$(dirname "$0")/.."

echo "--- TaleWeaver Docker Update ---"

# Pull latest changes from git
echo "[*] Pulling latest changes from Git..."
git pull

# Rebuild and restart
echo "[*] Rebuilding and restarting container..."
docker compose up -d --build --remove-orphans

echo "--------------------------------"
echo "[+] TaleWeaver has been updated and restarted!"
echo "--------------------------------"
