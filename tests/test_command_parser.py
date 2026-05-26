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


def test_take_command_routes_to_direct_take_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/take Ancient Key")
    assert response == "[TRIGGER_TAKE_DIRECT] Ancient Key"


def test_pickup_is_not_a_known_command() -> None:
    response = CommandParser.parse_command(_avatar(), "/pickup Ancient Key")
    assert "Unknown command" in response


def test_push_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/push Lever")
    assert response == "[TRIGGER_PUSH] Lever"


def test_pull_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/pull Chain")
    assert response == "[TRIGGER_PULL] Chain"


def test_talk_and_chat_commands_are_not_known() -> None:
    talk_response = CommandParser.parse_command(_avatar(), "/talk Guard")
    chat_response = CommandParser.parse_command(_avatar(), "/chat Guard")
    assert "Unknown command" in talk_response
    assert "Unknown command" in chat_response


def test_search_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/search Desk")
    assert response == "[TRIGGER_SEARCH] Desk"


def test_lookaround_and_rest_commands_return_triggers() -> None:
    look = CommandParser.parse_command(_avatar(), "/lookaround")
    rest = CommandParser.parse_command(_avatar(), "/rest")
    assert look == "[TRIGGER_LOOKAROUND]"
    assert rest == "[TRIGGER_REST]"


def test_open_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/open Rusty Chest")
    assert response == "[TRIGGER_OPEN] Rusty Chest"


def test_read_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/read Captain Log")
    assert response == "[TRIGGER_READ] Captain Log"


def test_unknown_commands_are_rejected() -> None:
    first_response = CommandParser.parse_command(_avatar(), "/foobar")
    second_response = CommandParser.parse_command(_avatar(), "/legacy_command")
    assert "Unknown command" in first_response
    assert "Unknown command" in second_response
