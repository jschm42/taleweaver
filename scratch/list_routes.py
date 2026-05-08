
import sys
import os

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.main import app

for route in app.routes:
    if hasattr(route, "path"):
        methods = getattr(route, "methods", [])
        print(f"{methods} {route.path}")
