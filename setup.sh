#!/bin/bash
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
ENV_CONTENT=$(cat .env)

# Determine python command
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    PYTHON_CMD="./venv/Scripts/python"
else
    PYTHON_CMD="./venv/bin/python3"
fi

# ENCRYPTION_KEY
if ! echo "$ENV_CONTENT" | grep -qE "ENCRYPTION_KEY=[a-zA-Z0-9\-_]{20,}"; then
    echo "[*] Generating ENCRYPTION_KEY..."
    KEY=$($PYTHON_CMD -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$KEY/" .env
    else
        sed -i "s/ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$KEY/" .env
    fi
    echo "[+] ENCRYPTION_KEY added to .env"
fi

# SECRET_KEY
if ! echo "$ENV_CONTENT" | grep -qE "SECRET_KEY=[a-fA-F0-9]{64}"; then
    echo "[*] Generating SECRET_KEY..."
    SKEY=$($PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=$SKEY/" .env
    else
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SKEY/" .env
    fi
    echo "[+] SECRET_KEY added to .env"
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
