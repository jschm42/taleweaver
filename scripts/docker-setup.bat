@echo off
REM TaleWeaver Docker Setup Script for Windows

cd %~dp0\..

echo --- TaleWeaver Docker Setup ---

IF NOT EXIST .env (
    echo [!] .env file not found. Creating from .env.example...
    copy .env.example .env
    echo [i] Please edit the .env file and set your ENCRYPTION_KEY and API keys.
)

IF NOT EXIST data (
    echo [*] Creating data directory...
    mkdir data
)

echo [*] Building and starting container...
docker compose up -d --build

echo --------------------------------
echo [+] TaleWeaver is now running!
echo [+] Access the UI at: http://localhost:8000 (check .env for BACKEND_PORT)
echo [+] Logs: docker compose logs -f
echo --------------------------------
pause
