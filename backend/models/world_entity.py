import uuid
from sqlalchemy import Column, String, JSON, Boolean, ForeignKey, Integer
from sqlalchemy.orm import synonym
from backend.models.base import Base, TimestampMixin

class WorldScene(Base, TimestampMixin):
    """
    A pre-generated location in the game world.
    """
    __tablename__ = "world_scenes"

    pk = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String(50), nullable=False) # Unique within an adventure (e.g. "FOREST_START")
    template_id = Column(String(36), ForeignKey("adventure_templates.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(36), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=True)
    
    label = Column(String(100), nullable=False) # Human readable name
    description = Column(String(2000), nullable=False) # Atmospheric description
    image_url = Column(String(255), nullable=True) # Scene visual link
    adventure_id = synonym("template_id")

class WorldExit(Base, TimestampMixin):
    """
    A connection between two scenes, with optional lock state.
    """
    __tablename__ = "world_exits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String(36), ForeignKey("adventure_templates.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(36), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=True)
    
    from_scene_id = Column(String(50), nullable=False)
    to_scene_id = Column(String(50), nullable=False)
    
    label = Column(String(100), nullable=False) # e.g. "a heavy oak door"
    is_locked = Column(Boolean, default=False, nullable=False)
    lock_description = Column(String(255), nullable=True) # e.g. "The door is bolted from the other side."
    adventure_id = synonym("template_id")

class WorldEntity(Base, TimestampMixin):
    """
    An NPC or Object that exists within the world and has a position.
    """
    __tablename__ = "world_entities"

    pk = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String(50), nullable=False) # e.g. "OLD_LIBRARIAN"
    template_id = Column(String(36), ForeignKey("adventure_templates.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(36), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=True)
    
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
    
    is_portable = Column(Boolean, default=True, nullable=False)
    combination_ingredients = Column(JSON, nullable=True) # List of entity IDs
    reveals_item_id = Column(String(50), nullable=True)
    is_final_state = Column(Boolean, default=False, nullable=False)
    state_comment = Column(String(1000), nullable=True)

    # NPC Specific Fields
    npc_type = Column(String(50), nullable=True) # HUMANOID, ANIMAL, MONSTER, BEING
    movement_type = Column(String(50), nullable=True) # STATIONARY, MOVABLE
    hp = Column(JSON, nullable=True) # Store as JSON to allow for {current: 10, max: 10} or similar if needed, or just Integer. User asked for Hitpoints.
    # Actually, let's keep it simple as Integers since user said "Hitpoints, Mana, Stamina"
    hp = Column(Integer, nullable=True)
    max_hp = Column(Integer, nullable=True)
    mana = Column(Integer, nullable=True)
    max_mana = Column(Integer, nullable=True)
    stamina = Column(Integer, nullable=True)
    max_stamina = Column(Integer, nullable=True)
    voice = Column(String(50), nullable=True) # Optional Google TTS voice for this NPC

    # Stat Modifiers
    stat_modifier_strength = Column(Integer, nullable=True)
    stat_modifier_dexterity = Column(Integer, nullable=True)
    stat_modifier_intelligence = Column(Integer, nullable=True)
    stat_modifier_wisdom = Column(Integer, nullable=True)
    stat_modifier_charisma = Column(Integer, nullable=True)
    stat_modifier_armor_class = Column(Integer, nullable=True)
    is_attackable = Column(Boolean, default=True, nullable=False)

    # Optional state, e.g. NPC inventory: [{"name": "Key", "id": "BRONZE_KEY"}]
    inventory = Column(JSON, default=list, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False) # For stats or dynamic state
    adventure_id = synonym("template_id")
