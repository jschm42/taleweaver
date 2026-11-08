#!/bin/bash

# TaleWeaver Docker Update Script
# This script pulls the latest changes and recreates the container.

set -e

# Navigate to project root
cd "$(dirname "$0")/.."

echo "--- TaleWeaver Docker Update ---"

# Pull latest changes from git
echo "[*] Pulling latest changes from Git..."
OLD_HEAD="$(git rev-parse HEAD)"
git pull

# Rebuild and restart
echo "[*] Rebuilding and restarting container..."
docker compose up -d --build --remove-orphans

# nginx.conf is bind-mounted as a single file. `git pull` replaces the file (new inode), so the
# running container keeps seeing the old one, and `up -d` does not recreate nginx because its
# image and compose definition did not change. Recreate it whenever the nginx config changed.
if ! git diff --quiet "$OLD_HEAD" HEAD -- nginx/ docker-compose.yml; then
    echo "[*] nginx configuration changed, recreating nginx..."
    docker compose up -d --force-recreate --no-deps nginx
fi

echo "--------------------------------"
echo "[+] TaleWeaver has been updated and restarted!"
echo "--------------------------------"
