from backend.crud.base import CRUDBase
from backend.models.adventure import Adventure
from backend.schemas.adventure import AdventureCreate, AdventureUpdate

class CRUDAdventure(CRUDBase[Adventure, AdventureCreate, AdventureUpdate]):
    pass

adventure = CRUDAdventure(Adventure)
