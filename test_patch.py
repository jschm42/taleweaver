import requests

url = "http://localhost:8000/api/adventures/test"
payload = {
    "title": "Test",
    "selected_image_styles": [{"id": "test", "name": "test"}],
    "selected_tone": {"id": "test", "name": "test"}
}
resp = requests.patch(url, json=payload)
print(resp.status_code)
print(resp.text)
