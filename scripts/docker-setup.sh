#!/bin/bash

# TaleWeaver Docker Setup Script
# This script builds and starts the TaleWeaver container with Nginx Reverse Proxy.

# Navigate to project root
cd "$(dirname "$0")/.."

echo "--- TaleWeaver Docker Setup ---"

# Check for .env file
if [ ! -f .env ]; then
    echo "[!] .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "[i] Please edit the .env file and set your ENCRYPTION_KEY and API keys."
fi

# Read FRONTEND_PORT and DOCKER_DATA_DIR from .env
FRONTEND_PORT=$(grep FRONTEND_PORT .env | cut -d '=' -f2 | tr -d '\r')
FRONTEND_PORT=${FRONTEND_PORT:-443}

DOCKER_DATA_DIR=$(grep DOCKER_DATA_DIR .env | cut -d '=' -f2 | tr -d '\r')
DOCKER_DATA_DIR=${DOCKER_DATA_DIR:-./data-docker}

# Create data directory if it doesn't exist
mkdir -p "$DOCKER_DATA_DIR"

# Ensure nginx directories exist
mkdir -p nginx/ssl

# Fix common Docker mount issue on Linux (where Docker creates a dir if file is missing)
if [ -d "nginx/nginx.conf" ]; then
    echo "[!] nginx/nginx.conf is a directory. Removing it to allow file mount..."
    rm -rf nginx/nginx.conf
fi

# Create default nginx.conf if missing
if [ ! -f "nginx/nginx.conf" ]; then
    echo "[*] Creating default nginx.conf..."
    cat <<EOF > nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    sendfile        on;
    keepalive_timeout  65;

    # Gzip settings
    gzip on;
    gzip_disable "msie6";
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_buffers 16 8k;
    gzip_http_version 1.1;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # HTTP redirect to HTTPS
    server {
        listen 80;
        server_name localhost;

        location / {
            return 301 https://\$host\$request_uri;
        }
    }

    # HTTPS server
    server {
        listen 443 ssl;
        server_name localhost;

        ssl_certificate /etc/nginx/ssl/nginx.crt;
        ssl_certificate_key /etc/nginx/ssl/nginx.key;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        location / {
            proxy_pass http://taleweaver:8000;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            
            # Increase client_max_body_size for large adventure uploads
            client_max_body_size 50M;
        }
    }
}
EOF
fi

# Generate SSL certificate if it doesn't exist
if [ ! -f nginx/ssl/nginx.crt ]; then
    echo "[*] Generating self-signed SSL certificate..."
    docker run --rm -v "$(pwd)/nginx/ssl:/export" alpine sh -c "apk add --no-cache openssl && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /export/nginx.key -out /export/nginx.crt -subj '/CN=localhost'"
fi

# Build and start
echo "[*] Building and starting container..."
docker compose up -d --build

if [ $? -ne 0 ]; then
    echo "[!] Docker build failed. Please check the error messages above."
    exit 1
fi

echo "--------------------------------"
echo "[+] TaleWeaver is now running with HTTPS!"
echo "[+] Access the UI at: https://localhost:$FRONTEND_PORT"
echo "[+] (Example adventures are being imported automatically)"
echo "[+] Logs: docker compose logs -f"
echo "--------------------------------"
