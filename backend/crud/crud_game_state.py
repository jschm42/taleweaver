from backend.crud.base import CRUDBase
from backend.models.game_state import GameState
from backend.schemas.game_state import GameStateCreate, GameStateUpdate

class CRUDGameState(CRUDBase[GameState, GameStateCreate, GameStateUpdate]):
    pass

game_state = CRUDGameState(GameState)
