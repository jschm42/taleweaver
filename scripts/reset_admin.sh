#!/bin/bash
# TaleWeaver Admin Reset Script

# Navigate to the project root
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/.."

# Use the project's environment (the system Python lacks the dependencies):
# Poetry first, then a local .venv, then the system Python (e.g. inside Docker).
if command -v poetry &>/dev/null && poetry env info -p &>/dev/null; then
    PYTHON_CMD=(poetry run python)
elif [ -x .venv/bin/python ]; then
    PYTHON_CMD=(.venv/bin/python)
elif [ -x .venv/Scripts/python.exe ]; then
    PYTHON_CMD=(.venv/Scripts/python.exe)
elif command -v python3 &>/dev/null; then
    PYTHON_CMD=(python3)
elif command -v python &>/dev/null; then
    PYTHON_CMD=(python)
else
    echo "Error: Python is not installed."
    exit 1
fi

# Run the reset script
"${PYTHON_CMD[@]}" scripts/reset_admin.py "$@"
