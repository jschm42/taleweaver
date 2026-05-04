import sys
import re

with open("tests/test_adventures_api.py", "r") as f:
    content = f.read()

content = content.replace('client.post("/api/adventures"', 'client.post("/api/adventures/"')
content = content.replace('client.post(\n        "/api/adventures"', 'client.post(\n        "/api/adventures/"')
content = content.replace('client.get("/api/adventures")', 'client.get("/api/adventures/sessions")')

with open("tests/test_adventures_api.py", "w") as f:
    f.write(content)
