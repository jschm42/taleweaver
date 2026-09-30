# TaleWeaver Setup Script (PowerShell)
# This script sets up the Python environment, database, and frontend dependencies.

param (
    [switch]$SkipStart
)

$ErrorActionPreference = "Stop"
Write-Host "--- TaleWeaver Setup ---" -ForegroundColor Cyan

# 1. Environment Variables (.env)
if (-not (Test-Path ".env")) {
    Write-Host "[*] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

$envFile = Get-Content ".env" -Raw
if ($envFile -notmatch "PROJECT_NAME=") {
    $envFile = "PROJECT_NAME=`"TaleWeaver`"`r`n" + $envFile
} else {
    $envFile = $envFile -replace "PROJECT_NAME=.*", "PROJECT_NAME=`"TaleWeaver`""
}
Set-Content ".env" $envFile

# 2. Dependency Management (Poetry)
Write-Host "[*] Setting up Python dependencies with Poetry..." -ForegroundColor Yellow
if (Get-Command poetry -ErrorAction SilentlyContinue) {
    Write-Host "[+] Using system Poetry..." -ForegroundColor Green
    poetry install
    $RUN_CMD = "poetry run"
} else {
    Write-Host "[*] Poetry not found in PATH. Checking virtual environment (venv)..." -ForegroundColor Yellow
    if (-not (Test-Path "venv")) {
        Write-Host "[*] Creating virtual environment (venv)..." -ForegroundColor Yellow
        python -m venv venv
    }
    Write-Host "[*] Installing Poetry and dependencies in venv..." -ForegroundColor Yellow
    .\venv\Scripts\python.exe -m pip install --upgrade pip
    .\venv\Scripts\pip.exe install "poetry>=2.0.0"
    .\venv\Scripts\poetry.exe install
    $RUN_CMD = ".\venv\Scripts\poetry.exe run"
}

# 4. Security Keys
if (-not (Test-Path "data")) {
    Write-Host "[*] Creating data directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "data" | Out-Null
}

# Helper: set or append a key=value pair in .env
# If the key line already exists it is replaced, otherwise appended.
function Set-EnvKey {
    param([string]$Key, [string]$Value)
    $content = Get-Content ".env" -Raw
    if ($content -match "(?m)^${Key}=") {
        $content = $content -replace "(?m)^${Key}=.*", "${Key}=${Value}"
    } else {
        $content = $content.TrimEnd() + "`r`n${Key}=${Value}`r`n"
    }
    Set-Content ".env" $content -NoNewline
}

$envFile = Get-Content ".env" -Raw

# ENCRYPTION_KEY
if ($envFile -notmatch "(?m)^ENCRYPTION_KEY=[a-zA-Z0-9+/=_-]{20,}") {
    Write-Host "[*] Generating ENCRYPTION_KEY..." -ForegroundColor Yellow
    $key = Invoke-Expression "$RUN_CMD python -c `"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())`""
    Set-EnvKey "ENCRYPTION_KEY" $key
    Write-Host "[+] ENCRYPTION_KEY written to .env" -ForegroundColor Green
}

# SECRET_KEY
$envFile = Get-Content ".env" -Raw
if ($envFile -notmatch "(?m)^SECRET_KEY=[a-fA-F0-9]{64}") {
    Write-Host "[*] Generating SECRET_KEY..." -ForegroundColor Yellow
    $skey = Invoke-Expression "$RUN_CMD python -c `"import secrets; print(secrets.token_hex(32))`""
    Set-EnvKey "SECRET_KEY" $skey
    Write-Host "[+] SECRET_KEY written to .env" -ForegroundColor Green
}


# 5. Database Setup (Migrations)
Write-Host "[*] Running database migrations..." -ForegroundColor Yellow
Invoke-Expression "$RUN_CMD alembic upgrade head"

# 6. Frontend Setup
Write-Host "[*] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location frontend
npm install
Set-Location ..

Write-Host "`n--- Setup Complete! ---" -ForegroundColor Green
Write-Host "To start the application:"
Write-Host "Backend: $RUN_CMD python -m backend.main  (or: $RUN_CMD taleweaver)"
Write-Host "Frontend: cd frontend; npm run dev`n"

# 7. Start (Optional / Interactive)
if (-not $SkipStart) {
    $start = Read-Host "Would you like to start the application now? (y/n)"
    if ($start -eq "y") {
        Write-Host "[*] Starting backend and frontend in new windows..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "$RUN_CMD python -m backend.main"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
    }
}
