"""Pydantic schemas for the script editor's AI assistant (optimize / generate)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

SCRIPT_ASSIST_CODE_MAX = 20000
SCRIPT_ASSIST_INSTRUCTION_MAX = 2000


class ScriptAssistRequest(BaseModel):
    mode: Literal["optimize", "generate"] = Field(
        ...,
        description=(
            "'optimize' improves and fixes the current code and fills placeholder comments; "
            "'generate' writes code for the instruction, building on the current code."
        ),
    )
    code: str = Field("", max_length=SCRIPT_ASSIST_CODE_MAX, description="Current editor code.")
    instruction: str = Field(
        "",
        max_length=SCRIPT_ASSIST_INSTRUCTION_MAX,
        description="What the author wants (required for 'generate', optional hint otherwise).",
    )
    context: str = Field(
        "general",
        max_length=60,
        description="Trigger context of the editor, e.g. 'on_pickup' or 'guard_expression'.",
    )
    label: str = Field("", max_length=120, description="Editor label, e.g. 'On Pickup Script'.")


class ScriptAssistResponse(BaseModel):
    code: Optional[str] = Field(None, description="The proposed code; None when the AI failed.")
    summary: Optional[str] = Field(None, description="Short English summary of the changes.")
    syntax_errors: list[str] = Field(
        default_factory=list,
        description="Sandbox check errors the proposal still has (empty when it is valid).",
    )
    error: Optional[str] = Field(
        None, description="User-safe failure description; HTTP status stays 200."
    )
