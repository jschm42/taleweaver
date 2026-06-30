# TaleWeaver Run Script (PowerShell)
# This script pulls the latest Git changes, checks setup status, offers to setup if incomplete, and runs the app.

$ErrorActionPreference = "Stop"

# Change directory to the repository root directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($scriptPath) {
    Set-Location $scriptPath
}

Write-Host "==============================" -ForegroundColor Green
Write-Host "      TaleWeaver Runner       " -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Green

# 1. Fetch current stand from Git
if (Test-Path ".git") {
    Write-Host "[*] Fetching latest changes from Git..." -ForegroundColor Cyan
    try {
        git pull
    } catch {
        Write-Host "[!] Warning: Git pull failed. Continuing anyway..." -ForegroundColor Yellow
    }
} else {
    Write-Host "[!] Not a Git repository, skipping Git pull." -ForegroundColor Yellow
}

# 2. Check setup status
$setupNeeded = $false
if (-not (Test-Path ".env")) { $setupNeeded = $true }
if (-not (Test-Path "venv")) { $setupNeeded = $true }
if (-not (Test-Path "frontend/node_modules")) { $setupNeeded = $true }

if ($setupNeeded) {
    Write-Host "[!] Project setup is missing or incomplete (missing .env, venv, or node_modules)." -ForegroundColor Yellow
    $choice = Read-Host "Would you like to run the setup script now? (y/n)"
    if ($choice -eq "y" -or $choice -eq "Y") {
        Write-Host "[*] Running setup.ps1..." -ForegroundColor Cyan
        & .\setup.ps1 -SkipStart
        # Re-check after setup runs
        if (-not (Test-Path ".env") -or -not (Test-Path "venv") -or -not (Test-Path "frontend/node_modules")) {
            Write-Host "[!] Setup failed or is still incomplete. Exiting." -ForegroundColor Red
            Exit 1
        }
    } else {
        $startAnyway = Read-Host "Would you like to try starting the application anyway? (y/n)"
        if ($startAnyway -ne "y" -and $startAnyway -ne "Y") {
            Write-Host "[*] Exiting."
            Exit 0
        }
    }
}

# 3. Start the application locally
Write-Host "[*] Starting backend and frontend..." -ForegroundColor Green

if ($IsWindows -or $env:OS -like "*Windows*") {
    # On Windows, we can start them in separate PowerShell windows
    Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\python.exe -m backend.main"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
    Write-Host "[+] Application started in separate PowerShell windows." -ForegroundColor Green
} else {
    # Non-Windows PowerShell fallback (macOS/Linux)
    Write-Host "[*] Starting processes in background..." -ForegroundColor Green
    Start-Job -ScriptBlock { cd backend; ../venv/bin/python3 -m backend.main }
    Start-Job -ScriptBlock { cd frontend; npm run dev }
    Write-Host "[+] Jobs started. Use 'Get-Job' to check status, or 'Stop-Job' to stop them." -ForegroundColor Green
}
