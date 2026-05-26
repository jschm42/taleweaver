from datetime import datetime
from typing import Literal

from pydantic import BaseModel


CheckpointTriggerReason = Literal[
    "SCENE_CHANGE",
    "QUEST_UPDATE",
    "AWARD_GRANTED",
]


class SessionCheckpointResponse(BaseModel):
    id: str
    session_id: str
    message_index: int
    trigger_reason: CheckpointTriggerReason
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RestoreCheckpointResponse(BaseModel):
    status: str
    checkpoint_id: str
    deleted_messages: int
