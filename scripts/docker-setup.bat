@echo off
REM TaleWeaver Docker Setup Script for Windows

cd %~dp0\..

echo --- TaleWeaver Docker Setup ---

IF NOT EXIST .env (
    echo [!] .env file not found. Creating from .env.example...
    copy .env.example .env
    echo [i] Please edit the .env file and set your ENCRYPTION_KEY and API keys.
)

REM Read FRONTEND_PORT from .env
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="FRONTEND_PORT" set FRONTEND_PORT=%%b
)
IF "%FRONTEND_PORT%"=="" set FRONTEND_PORT=443

IF NOT EXIST data (
    echo [*] Creating data directory...
    mkdir data
)

IF NOT EXIST nginx\ssl\nginx.crt (
    echo [*] Generating self-signed SSL certificate...
    docker run --rm -v "%cd%\nginx\ssl:/export" alpine sh -c "apk add --no-cache openssl && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /export/nginx.key -out /export/nginx.crt -subj '/CN=localhost'"
)

echo [*] Building and starting container...
docker compose up -d --build
IF %ERRORLEVEL% NEQ 0 (
    echo [!] Docker build failed. Please check the error messages above.
    pause
    exit /b %ERRORLEVEL%
)

echo --------------------------------
echo [+] TaleWeaver is now running with HTTPS!
echo [+] Access the UI at: https://localhost:%FRONTEND_PORT%
echo [+] (Example adventures are being imported automatically)
echo [+] Logs: docker compose logs -f
echo --------------------------------
pause
