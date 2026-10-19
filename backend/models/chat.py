import uuid6
from sqlalchemy import Column, ForeignKey, String, Text, event, inspect
from sqlalchemy.orm import Session

from backend.models.base import Base, TimestampMixin
from backend.models.session_state import SessionState


class ChatMessage(Base, TimestampMixin):
    """
    Stores conversational history for the sliding-window memory management.
    """
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    session_id = Column(String(36), ForeignKey("game_sessions.id"), nullable=False)

    # "user", "assistant", or "system"
    role = Column(String(20), nullable=False)

    # The actual message payload
    content = Column(Text, nullable=False)

    # Scene and sequence the message was written in. The client groups the story into
    # one page per scene/sequence. Stamped automatically on flush (see below).
    scene_id = Column(String(100), nullable=True)
    sequence_id = Column(String(100), nullable=True)

    def to_client_dict(self) -> dict:
        """Chat history entry as sent to the client."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "scene_id": self.scene_id,
            "sequence_id": self.sequence_id,
        }


def _loaded_session_states(session: Session) -> dict[str, SessionState]:
    states = [
        obj
        for obj in (*session.identity_map.values(), *session.new)
        if isinstance(obj, SessionState)
    ]
    return {state.session_id: state for state in states}


@event.listens_for(Session, "before_flush")
def _stamp_chat_scene_context(session: Session, _flush_context, _instances) -> None:
    """Stamps new chat messages with the session's current scene and sequence.

    Uses the SessionState already loaded in this DB session (the turn pipeline always has
    it). Only already-loaded attribute values are read, so no lazy load is triggered.
    """
    new_messages = [
        obj for obj in session.new if isinstance(obj, ChatMessage) and obj.scene_id is None
    ]
    if not new_messages:
        return
    states = _loaded_session_states(session)
    for message in new_messages:
        state = states.get(message.session_id)
        if state is None:
            continue
        loaded = inspect(state).dict
        message.scene_id = loaded.get("current_scene_id")
        message.sequence_id = loaded.get("active_sequence_id")
