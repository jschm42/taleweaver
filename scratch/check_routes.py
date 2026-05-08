
import sys
import os

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.main import app

print("Listing all registered routes:")
for route in app.routes:
    methods = getattr(route, "methods", "N/A")
    path = getattr(route, "path", getattr(route, "path_format", "N/A"))
    print(f"{methods} {path}")

print("\nChecking for specific route:")
target = "/api/adventures/{template_id}/visuals/suggest-prompt"
found = False
for route in app.routes:
    path = getattr(route, "path", None)
    if path == target:
        found = True
        print(f"Found match: {path}")

if not found:
    print(f"Route NOT FOUND: {target}")
