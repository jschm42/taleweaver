from backend.schemas.adventure import AdventureTemplateUpdate
from pydantic import ValidationError

try:
    obj = AdventureTemplateUpdate(time_per_turn="")
    print("OK")
except ValidationError as e:
    print(e.json())
