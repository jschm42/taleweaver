#!/usr/bin/env python3
"""Backward-compatible wrapper for scripts/generate_keys.py --fernet."""
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parent / "generate_keys.py"
sys.exit(subprocess.call([sys.executable, str(_SCRIPT), "--fernet"] + sys.argv[1:]))
