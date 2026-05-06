@echo off
setlocal enabledelayedexpansion

REM TaleWeaver Docker Setup Script
REM This script builds and starts the TaleWeaver container with Nginx Reverse Proxy.

echo --- TaleWeaver Docker Setup ---

IF NOT EXIST .env (
    echo [!] .env file not found. Creating from .env.example...
    copy .env.example .env
    echo [i] Please edit the .env file and set your ENCRYPTION_KEY and API keys.
)

REM Read FRONTEND_PORT and DOCKER_DATA_DIR from .env
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="FRONTEND_PORT" set FRONTEND_PORT=%%b
    if "%%a"=="DOCKER_DATA_DIR" set DOCKER_DATA_DIR=%%b
)
IF "%FRONTEND_PORT%"=="" set FRONTEND_PORT=443
IF "%DOCKER_DATA_DIR%"=="" set DOCKER_DATA_DIR=./data-docker

IF NOT EXIST "%DOCKER_DATA_DIR%" (
    echo [*] Creating isolated data directory at %DOCKER_DATA_DIR%...
    mkdir "%DOCKER_DATA_DIR%"
)

IF NOT EXIST nginx (
    mkdir nginx
)

IF EXIST nginx\nginx.conf\ (
    echo [!] nginx\nginx.conf is a directory. Removing it...
    rmdir /s /q nginx\nginx.conf
)

IF NOT EXIST nginx\nginx.conf (
    echo [*] Creating default nginx.conf...
    (
    echo events {
    echo     worker_connections 1024;
    echo }
    echo.
    echo http {
    echo     include       /etc/nginx/mime.types;
    echo     default_type  application/octet-stream;
    echo.
    echo     sendfile        on;
    echo     keepalive_timeout  65;
    echo.
    echo     server {
    echo         listen 80;
    echo         server_name localhost;
    echo         location / {
    echo             return 301 https://$host$request_uri;
    echo         }
    echo     }
    echo.
    echo     server {
    echo         listen 443 ssl;
    echo         server_name localhost;
    echo         ssl_certificate /etc/nginx/ssl/nginx.crt;
    echo         ssl_certificate_key /etc/nginx/ssl/nginx.key;
    echo         ssl_protocols TLSv1.2 TLSv1.3;
    echo         ssl_ciphers HIGH:!aNULL:!MD5;
    echo.
    echo         location / {
    echo             proxy_pass http://taleweaver:8000;
    echo             proxy_set_header Host $host;
    echo             proxy_set_header X-Real-IP $remote_addr;
    echo             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    echo             proxy_set_header X-Forwarded-Proto $scheme;
    echo             proxy_http_version 1.1;
    echo             proxy_set_header Upgrade $http_upgrade;
    echo             proxy_set_header Connection "upgrade";
    echo             client_max_body_size 50M;
    echo         }
    echo     }
    echo }
    ) > nginx\nginx.conf
)

IF NOT EXIST nginx\ssl (
    mkdir nginx\ssl
)

IF NOT EXIST nginx\ssl\nginx.crt (
    echo [*] Generating self-signed SSL certificate...
    docker run --rm -v "%cd%\nginx\ssl:/export" alpine sh -c "apk add --no-cache openssl && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /export/nginx.key -out /export/nginx.crt -subj '/CN=localhost'"
)

echo [*] Building and starting container...
docker compose up -d --build

if %ERRORLEVEL% NEQ 0 (
    echo [!] Docker build failed. Please check the error messages above.
    exit /b %ERRORLEVEL%
)

echo --------------------------------
echo [+] TaleWeaver is now running with HTTPS!
echo [+] Access the UI at: https://localhost:%FRONTEND_PORT%
echo [+] (Example adventures are being imported automatically)
echo [+] Logs: docker compose logs -f
echo --------------------------------
pause
