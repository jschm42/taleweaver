# TaleWeaver Setup Script (PowerShell)
# This script sets up the Python environment, database, and frontend dependencies.

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

# 2. Python Virtual Environment
if (-not (Test-Path "venv")) {
    Write-Host "[*] Creating virtual environment (venv)..." -ForegroundColor Yellow
    python -m venv venv
}

# 3. Install Backend Dependencies
Write-Host "[*] Installing backend dependencies..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt

# 4. Encryption Key
if (-not (Test-Path "data")) {
    Write-Host "[*] Creating data directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "data" | Out-Null
}

$envFile = Get-Content ".env" -Raw
if ($envFile -notmatch "ENCRYPTION_KEY=[a-zA-Z0-9\-_]{20,}") {
    Write-Host "[*] Generating ENCRYPTION_KEY..." -ForegroundColor Yellow
    $key = .\venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    $envFile = $envFile -replace "ENCRYPTION_KEY=.*", "ENCRYPTION_KEY=$key"
    Set-Content ".env" $envFile
    Write-Host "[+] ENCRYPTION_KEY added to .env" -ForegroundColor Green
} else {
    Write-Host "[+] ENCRYPTION_KEY already exists in .env" -ForegroundColor Green
}

# 5. Database Setup (Migrations)
Write-Host "[*] Running database migrations..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m alembic upgrade head

# 6. Frontend Setup
Write-Host "[*] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location frontend
npm install
Set-Location ..

Write-Host "`n--- Setup Complete! ---" -ForegroundColor Green
Write-Host "To start the application:"
Write-Host "Backend: .\venv\Scripts\python.exe -m backend.main"
Write-Host "Frontend: cd frontend; npm run dev`n"

# 7. Start (Optional / Interactive)
$start = Read-Host "Would you like to start the application now? (y/n)"
if ($start -eq "y") {
    Write-Host "[*] Starting backend and frontend in new windows..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\python.exe -m backend.main"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
}
