from backend.crud.base import CRUDBase
from backend.models.adventure_template import AdventureTemplate
from backend.schemas.adventure import AdventureTemplateCreate, AdventureTemplateUpdate


class CRUDAdventureTemplate(CRUDBase[AdventureTemplate, AdventureTemplateCreate, AdventureTemplateUpdate]):
    pass

adventure_template = CRUDAdventureTemplate(AdventureTemplate)
