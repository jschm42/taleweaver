from backend.crud.base import CRUDBase
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.schemas.session import (
    GameSessionCreate,
    GameSessionUpdate,
    SessionStateCreate,
    SessionStateUpdate,
)


class CRUDGameSession(CRUDBase[GameSession, GameSessionCreate, GameSessionUpdate]):
    pass

class CRUDSessionState(CRUDBase[SessionState, SessionStateCreate, SessionStateUpdate]):
    pass

game_session = CRUDGameSession(GameSession)
session_state = CRUDSessionState(SessionState)
