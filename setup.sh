#!/usr/bin/env bash
# TaleWeaver Setup Script (Bash)
# This script sets up the Python environment, database, and frontend dependencies.

set -e

# Parse arguments
SKIP_START=false
for arg in "$@"; do
    if [ "$arg" == "--skip-start" ]; then
        SKIP_START=true
    fi
done

echo "--- TaleWeaver Setup ---"

# 1. Environment Variables (.env)
if [ ! -f .env ]; then
    echo "[*] Creating .env from .env.example..."
    cp .env.example .env
fi

if ! grep -q "PROJECT_NAME=" .env; then
    sed -i '1i PROJECT_NAME="TaleWeaver"' .env
else
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' 's/PROJECT_NAME=.*/PROJECT_NAME="TaleWeaver"/' .env
    else
        sed -i 's/PROJECT_NAME=.*/PROJECT_NAME="TaleWeaver"/' .env
    fi
fi

# 2. Dependency Management (Poetry)
echo "[*] Setting up Python dependencies with Poetry..."
if command -v poetry &> /dev/null; then
    echo "[+] Using system Poetry..."
    poetry install
    RUN_CMD="poetry run"
    PYTHON_CMD="poetry run python"
else
    echo "[*] Poetry not found in PATH. Checking virtual environment (venv)..."
    if [ ! -d "venv" ]; then
        echo "[*] Creating virtual environment (venv)..."
        python3 -m venv venv
    fi
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        ./venv/Scripts/pip install --upgrade pip "poetry>=2.0.0"
        ./venv/Scripts/poetry install
        RUN_CMD="./venv/Scripts/poetry run"
        PYTHON_CMD="./venv/Scripts/poetry run python"
    else
        ./venv/bin/pip install --upgrade pip "poetry>=2.0.0"
        ./venv/bin/poetry install
        RUN_CMD="./venv/bin/poetry run"
        PYTHON_CMD="./venv/bin/poetry run python"
    fi
fi


# 4. Security Keys
mkdir -p data

# Helper: set or append a key=value pair in .env
# Usage: set_env_key KEY VALUE
set_env_key() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" .env; then
        # Key line exists – replace it (macOS needs empty string after -i)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" .env
        else
            sed -i "s|^${key}=.*|${key}=${value}|" .env
        fi
    else
        # Key line missing entirely – append it
        echo "${key}=${value}" >> .env
    fi
}

# ENCRYPTION_KEY
if ! grep -qE "^ENCRYPTION_KEY=[a-zA-Z0-9+/=_-]{20,}" .env; then
    echo "[*] Generating ENCRYPTION_KEY..."
    KEY=$($PYTHON_CMD -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    set_env_key "ENCRYPTION_KEY" "$KEY"
    echo "[+] ENCRYPTION_KEY written to .env"
fi

# SECRET_KEY
if ! grep -qE "^SECRET_KEY=[a-fA-F0-9]{64}" .env; then
    echo "[*] Generating SECRET_KEY..."
    SKEY=$($PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
    set_env_key "SECRET_KEY" "$SKEY"
    echo "[+] SECRET_KEY written to .env"
fi

# 5. Database Setup (Migrations)
echo "[*] Running database migrations..."
$PYTHON_CMD -m alembic upgrade head

# 6. Frontend Setup
echo "[*] Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo -e "\n--- Setup Complete! ---"
echo "To start the application:"
echo "Backend: $RUN_CMD python -m backend.main (or: $RUN_CMD taleweaver)"
echo "Frontend: cd frontend && npm run dev"

# 7. Start (Optional)
if [ "$SKIP_START" = false ]; then
    echo
    read -p "Would you like to start the application now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "[*] Starting backend..."
        $RUN_CMD python -m backend.main &
        BACKEND_PID=$!
        
        echo "[*] Starting frontend..."
        cd frontend && npm run dev &
        FRONTEND_PID=$!
        
        echo "Processes started. PIDs: Backend=$BACKEND_PID, Frontend=$FRONTEND_PID"
        echo "Press Ctrl+C to stop (though background processes might need manual kill if shell exits)"
        wait
    fi
fi
