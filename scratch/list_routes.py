
from backend.main import app
for route in app.routes:
    print(f"{route.path} [{','.join(route.methods)}]")
