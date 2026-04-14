import uuid
from sqlalchemy import Column, String, JSON, Boolean, ForeignKey
from backend.models.base import Base, TimestampMixin

class WorldScene(Base, TimestampMixin):
    """
    A pre-generated location in the game world.
    """
    __tablename__ = "world_scenes"

    id = Column(String(50), primary_key=True) # Unique within an adventure (e.g. "FOREST_START")
    adventure_id = Column(String(36), ForeignKey("adventures.id"), primary_key=True)
    
    label = Column(String(100), nullable=False) # Human readable name
    description = Column(String(2000), nullable=False) # Atmospheric description
    image_url = Column(String(255), nullable=True) # Scene visual link

class WorldExit(Base, TimestampMixin):
    """
    A connection between two scenes, with optional lock state.
    """
    __tablename__ = "world_exits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    adventure_id = Column(String(36), ForeignKey("adventures.id"), nullable=False)
    
    from_scene_id = Column(String(50), nullable=False)
    to_scene_id = Column(String(50), nullable=False)
    
    label = Column(String(100), nullable=False) # e.g. "a heavy oak door"
    is_locked = Column(Boolean, default=False, nullable=False)
    lock_description = Column(String(255), nullable=True) # e.g. "The door is bolted from the other side."

class WorldEntity(Base, TimestampMixin):
    """
    An NPC or Object that exists within the world and has a position.
    """
    __tablename__ = "world_entities"

    id = Column(String(50), primary_key=True) # e.g. "OLD_LIBRARIAN"
    adventure_id = Column(String(36), ForeignKey("adventures.id"), primary_key=True)
    
    entity_type = Column(String(20), nullable=False) # "NPC" or "OBJECT"
    name = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=False)
    
    current_scene_id = Column(String(50), nullable=False)
    spatial_position = Column(String(255), nullable=True) # e.g. "inside the desk"
    image_url = Column(String(255), nullable=True)
    
    # Advanced Item Management
    item_type = Column(String(50), nullable=True) # e.g. "CONSUMABLE", "WEAPON", "KEY", "STATIC"
    wearable_slots = Column(JSON, nullable=True) # e.g. ["Head", "Neck"]
    is_in_inventory = Column(Boolean, default=False, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)
    
    # Optional state, e.g. NPC inventory: [{"name": "Key", "id": "BRONZE_KEY"}]
    inventory = Column(JSON, default=list, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False) # For stats or dynamic state
