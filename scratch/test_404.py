
import sys
import os
from fastapi.testclient import TestClient

# Add the current directory to sys.path to find 'backend'
sys.path.append(os.getcwd())

from backend.main import app

client = TestClient(app)

url = "/api/adventures/69529b8d-2989-4952-a457-ab4f141f3a2b/visuals/suggest-prompt"
print(f"Testing POST {url}...")

# We don't need auth for the routing check, but suggest_prompt requires it.
# However, 404 happens BEFORE auth usually if the path doesn't match.
# If it matches but auth fails, we get 401.

response = client.post(url, json={"target_type": "cover", "target_id": "test"})
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 404:
    print("\nRouting issue confirmed.")
else:
    print("\nRouting works, issue might be something else.")
