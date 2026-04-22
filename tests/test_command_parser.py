from backend.engine.command_parser import CommandParser
from backend.models.avatar import Avatar


def _avatar() -> Avatar:
    return Avatar(name="Tester", inventory=[], equipment={"Hands": None})


def test_help_includes_walkthrough_and_hint_commands() -> None:
    help_text = CommandParser.parse_command(_avatar(), "/help")
    assert "/walkthrough" in help_text
    assert "/hint" in help_text


def test_walkthrough_reveal_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/walkthrough reveal")
    assert response == "[TRIGGER_WALKTHROUGH_REVEAL]"


def test_hint_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/hint")
    assert response == "[TRIGGER_HINT]"
