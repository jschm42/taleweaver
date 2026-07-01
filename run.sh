#!/usr/bin/env bash
# TaleWeaver Run Script (Bash)
# This script pulls the latest Git changes, checks setup status, offers to setup if incomplete, and runs the app.

set -e

# Change directory to the repository root directory
cd "$(dirname "$0")"

echo "=============================="
echo "      TaleWeaver Runner       "
echo "=============================="

# 1. Fetch current stand from Git
if [ -d ".git" ]; then
    echo "[*] Fetching latest changes from Git..."
    git pull || echo "[!] Warning: Git pull failed. Continuing anyway..."
else
    echo "[!] Not a Git repository, skipping Git pull."
fi

# 2. Check setup status
SETUP_NEEDED=false
if [ ! -f .env ]; then SETUP_NEEDED=true; fi
if [ ! -d venv ]; then SETUP_NEEDED=true; fi
if [ ! -d frontend/node_modules ]; then SETUP_NEEDED=true; fi

if [ "$SETUP_NEEDED" = true ]; then
    echo "[!] Project setup is missing or incomplete (missing .env, venv, or node_modules)."
    read -rp "Would you like to run the setup script now? (y/n): " RUN_SETUP
    if [[ "$RUN_SETUP" =~ ^[Yy]$ ]]; then
        echo "[*] Running setup.sh..."
        bash ./setup.sh --skip-start
        # Re-check after setup runs
        if [ ! -f .env ] || [ ! -d venv ] || [ ! -d frontend/node_modules ]; then
            echo "[!] Setup failed or is still incomplete. Exiting."
            exit 1
        fi
    else
        read -rp "Would you like to try starting the application anyway? (y/n): " START_ANYWAY
        if [[ ! "$START_ANYWAY" =~ ^[Yy]$ ]]; then
            echo "[*] Exiting."
            exit 0
        fi
    fi
fi

# 3. Start the application locally
echo "[*] Starting backend and frontend..."

# Determine python path based on OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    PYTHON_CMD="./venv/Scripts/python"
else
    PYTHON_CMD="./venv/bin/python3"
fi

# Start backend in background
$PYTHON_CMD -m backend.main &
BACKEND_PID=$!

# Start frontend in background
echo "[*] Starting frontend..."
cd frontend && npm run dev &
FRONTEND_PID=$!

# Go back to root
cd ..

echo "Processes started. PIDs: Backend=$BACKEND_PID, Frontend=$FRONTEND_PID"
echo "Press Ctrl+C to stop both processes."

# Trap Ctrl+C to kill the background processes
trap 'echo -e "\nStopping backend and frontend..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT

wait
