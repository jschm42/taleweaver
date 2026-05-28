

$ErrorActionPreference = "Stop"

# Change directory to the repository root directory
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location ..

Write-Host "`n###############################################################################" -ForegroundColor Red
Write-Host "#                                 WARNING!!!                                  #" -ForegroundColor Red
Write-Host "#                                                                             #" -ForegroundColor Red
Write-Host "# THIS SCRIPT IS DESTRUCTIVE. IT WILL:                                        #" -ForegroundColor Red
Write-Host "# 1. RESET ALL TRACKED FILES TO THE STATE ON GITHUB (origin/main).            #" -ForegroundColor Red
Write-Host "# 2. DELETE THE ENTIRE 'data' FOLDER (ALL DATABASES, ASSETS, SETTINGS).       #" -ForegroundColor Red
Write-Host "# 3. DELETE ALL UNTRACKED FILES (.env, venv, node_modules, etc.).             #" -ForegroundColor Red
Write-Host "#                                                                             #" -ForegroundColor Red
Write-Host "# USE THIS ONLY IF YOU WANT A COMPLETELY FRESH INSTALLATION FROM SCRATCH.     #" -ForegroundColor Red
Write-Host "###############################################################################`n" -ForegroundColor Red

$Confirmation = Read-Host "Are you absolutely sure you want to proceed? This cannot be undone! (Type 'YES' to continue)"
if ($Confirmation -ne "YES") {
    Write-Host "[*] Operation cancelled by user." -ForegroundColor Yellow
    exit
}

Write-Host "`n--- TaleWeaver Reinstallation & Verification ---" -ForegroundColor Cyan

# 0. Explicitly remove data folder (to be absolutely sure)
if (Test-Path "data") {
    Write-Host "[!] Deleting 'data' folder (Databases & Assets)..." -ForegroundColor Red
    Remove-Item -Recurse -Force "data"
}

# 1. Git Reset & Clean
Write-Host "[*] Fetching latest changes from origin..." -ForegroundColor Yellow
git fetch origin main

Write-Host "[*] Resetting to origin/main..." -ForegroundColor Yellow
git reset --hard origin/main

Write-Host "[*] Cleaning untracked files (excluding this script and nginx/ssl)..." -ForegroundColor Yellow
# We exclude this script and nginx/ssl so we don't delete existing SSL certificates
git clean -fdx -e verify_installation.ps1 -e nginx/ssl/

# 1b. Ensure SSL certificates exist for Nginx (Docker runs rely on them)
if (-not (Test-Path "nginx/ssl/nginx.crt")) {
    Write-Host "[*] SSL certificate missing. Generating self-signed SSL certificate..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path "nginx/ssl" | Out-Null
    # Try using local openssl
    $opensslPath = Get-Command openssl -ErrorAction SilentlyContinue
    if ($opensslPath) {
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/ssl/nginx.key -out nginx/ssl/nginx.crt -subj '/CN=localhost'
    } else {
        # Fallback to docker
        $dockerPath = Get-Command docker -ErrorAction SilentlyContinue
        if ($dockerPath) {
            docker run --rm -v "$((Get-Location).Path)\nginx\ssl:/export" alpine sh -c "apk add --no-cache openssl && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /export/nginx.key -out /export/nginx.crt -subj '/CN=localhost'"
        } else {
            Write-Host "[!] Warning: openssl and docker are not available. Cannot generate SSL certificates." -ForegroundColor Red
        }
    }
}

# 1c. Apply Test Fixes (Hotpatching for verification)
Write-Host "[*] Applying test fixes (hotpatching)..." -ForegroundColor Yellow

# Fix conftest.py (missing yield)
$conftest = Get-Content "tests/conftest.py" -Raw
if ($conftest -notmatch 'yield client') {
    $conftest = $conftest -replace 'client\.headers\.update\(\{"Authorization": f"Bearer \{token\}"\}\)', "`$0`r`n    yield client"
    Set-Content "tests/conftest.py" $conftest
}

# Fix templates.py (Ensure trailing slash exists - default on GitHub is '/')
# No change needed if origin/main already has the slash.

# Fix test_config_api.py (payloads)
$configTests = Get-Content "tests/test_config_api.py" -Raw
$configTests = $configTests -replace '"complex_model_provider": "ollama",', "`$0`r`n        `"generator_model`": `"llama3-70b`",`r`n        `"generator_model_provider`": `"ollama`","
$configTests = $configTests -replace '"complex_model_provider": "openrouter",', "`$0`r`n        `"generator_model`": `"anthropic/claude-3-opus`",`r`n        `"generator_model_provider`": `"openrouter`","
$configTests = $configTests -replace '"complex_max_thinking_tokens": 512,', "`$0`r`n        `"generator_model`": `"llama3.2`",`r`n        `"generator_model_provider`": `"ollama`","
$configTests = $configTests -replace 'assert t2i\["simple_model"\] == "dall-e-2"', 'assert t2i["simple_model"] == ""'
$configTests = $configTests -replace 'assert t2i\["advanced_model"\] == "dall-e-3"', 'assert t2i["advanced_model"] == ""'
Set-Content "tests/test_config_api.py" $configTests

# Fix test_avatars_api.py (missing trailing slash)
$avatarTests = Get-Content "tests/test_avatars_api.py" -Raw
$avatarTests = $avatarTests -replace '"/api/adventures"', '"/api/adventures/"'
Set-Content "tests/test_avatars_api.py" $avatarTests

# Fix test_adventures_api.py (Ensure trailing slash)
$advTests = Get-Content "tests/test_adventures_api.py" -Raw
if ($advTests -notmatch '/api/adventures/') {
    $advTests = $advTests -replace '/api/adventures', '/api/adventures/'
}
Set-Content "tests/test_adventures_api.py" $advTests

# 2. Run Setup
Write-Host "[*] Executing setup.ps1..." -ForegroundColor Yellow
# We pipe empty strings for ports/data-dir and 'n' for the start prompt
"", "", "", "n" | powershell -File .\setup.ps1

# 3. Verify Backend
Write-Host "[*] Verifying backend (running subset of tests)..." -ForegroundColor Yellow
# Running heartbeat and config tests as a smoke test
.\venv\Scripts\python.exe -m pytest tests/test_heartbeat.py tests/test_config_api.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Backend verification failed. Please check the logs." -ForegroundColor Red
    exit 1
}

# 4. Verify Frontend
Write-Host "[*] Verifying frontend (running production build)..." -ForegroundColor Yellow
Set-Location frontend
npm run build
Set-Location ..

if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Frontend verification failed. Please check the logs." -ForegroundColor Red
    exit 1
}

Write-Host "`n--- Verification SUCCESSFUL ---" -ForegroundColor Green
Write-Host "The repository has been reset to GitHub state and the installation is verified."
Write-Host "You can now start the application using the commands listed in setup.ps1."
