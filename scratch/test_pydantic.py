from pydantic import BaseModel, Field
from typing import List, Optional

class QuestSchema(BaseModel):
    id: str
    title: str

class WorldManifesto(BaseModel):
    quests: List[QuestSchema] = Field(default_factory=list)

manifesto = WorldManifesto(quests=[QuestSchema(id="Q1", title="Test")])
print(f"Dump: {manifesto.model_dump()}")

empty_manifesto = WorldManifesto()
print(f"Empty Dump: {empty_manifesto.model_dump()}")
