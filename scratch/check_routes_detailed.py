
import sys
import os

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.main import app

print(f"{'Method':<10} {'Path':<60} {'Endpoint'}")
print("-" * 100)
for route in app.routes:
    methods = getattr(route, "methods", {"N/A"})
    path = getattr(route, "path", getattr(route, "path_format", "N/A"))
    endpoint = getattr(route, "endpoint", None)
    endpoint_name = endpoint.__name__ if endpoint else "N/A"
    
    method_str = ", ".join(methods)
    print(f"{method_str:<10} {path:<60} {endpoint_name}")

print("\nSearching for suggest-prompt specifically...")
for route in app.routes:
    path = getattr(route, "path", "")
    if "suggest-prompt" in path:
        methods = getattr(route, "methods", {"N/A"})
        endpoint = getattr(route, "endpoint", None)
        endpoint_name = endpoint.__name__ if endpoint else "N/A"
        print(f"FOUND: {methods} {path} -> {endpoint_name}")
