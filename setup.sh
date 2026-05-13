#!/usr/bin/env bash
# TaleWeaver Setup Script (Bash)
# This script sets up the Python environment, database, and frontend dependencies.

set -e

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

# 2. Python Virtual Environment
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment (venv)..."
    python3 -m venv venv
fi

# 3. Install Backend Dependencies
echo "[*] Installing backend dependencies..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows-based shells (Git Bash, etc.)
    ./venv/Scripts/pip install --upgrade pip
    ./venv/Scripts/pip install -r requirements.txt
else
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

# 4. Security Keys
mkdir -p data

# Determine python command
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    PYTHON_CMD="./venv/Scripts/python"
else
    PYTHON_CMD="./venv/bin/python3"
fi

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
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "Backend: ./venv/Scripts/python -m backend.main"
else
    echo "Backend: ./venv/bin/python3 -m backend.main"
fi
echo "Frontend: cd frontend && npm run dev"

# 7. Start (Optional)
echo
read -p "Would you like to start the application now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "[*] Starting backend..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        ./venv/Scripts/python -m backend.main &
    else
        ./venv/bin/python3 -m backend.main &
    fi
    BACKEND_PID=$!
    
    echo "[*] Starting frontend..."
    cd frontend && npm run dev &
    FRONTEND_PID=$!
    
    echo "Processes started. PIDs: Backend=$BACKEND_PID, Frontend=$FRONTEND_PID"
    echo "Press Ctrl+C to stop (though background processes might need manual kill if shell exits)"
    wait
fi
