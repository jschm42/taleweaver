
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
ADV_ID = "69529b8d-2989-4952-a457-ab4f141f3a2b"

def test_suggest_prompt():
    url = f"{BASE_URL}/adventures/{ADV_ID}/visuals/suggest-prompt"
    payload = {
        "target_type": "cover",
        "target_id": ADV_ID
    }
    # Note: This will likely fail with 401/403 since I don't have a token,
    # but it should NOT be 404 if the route exists.
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    test_suggest_prompt()
