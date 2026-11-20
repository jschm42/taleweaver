from backend.engine.interaction.command_parser import CommandParser
from backend.models.avatar import Avatar


def _avatar() -> Avatar:
    return Avatar(name="Tester", inventory=[], equipment={"Hands": None})


def test_help_includes_walkthrough_command_and_not_hint() -> None:
    help_text = CommandParser.parse_command(_avatar(), "/help")
    assert "/walkthrough" in help_text
    assert "/hint" not in help_text


def test_walkthrough_reveal_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/walkthrough reveal")
    assert response == "[TRIGGER_WALKTHROUGH_REVEAL]"


def test_hint_is_not_a_known_command() -> None:
    response = CommandParser.parse_command(_avatar(), "/hint")
    assert "Unknown command" in response


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


def test_switch_command_returns_trigger() -> None:
    response = CommandParser.parse_command(_avatar(), "/switch POWER_CORE HIGH 7391")
    assert response == "[TRIGGER_SWITCH] POWER_CORE HIGH 7391"


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


def test_greet_command_returns_trigger_and_is_listed_in_help() -> None:
    response = CommandParser.parse_command(_avatar(), "/greet Bram")
    help_text = CommandParser.parse_command(_avatar(), "/help")
    assert response == "[TRIGGER_GREET] Bram"
    assert "/greet" in help_text


def test_equip_wearable_slots_resolves_correctly() -> None:
    avatar = Avatar(
        name="Tester",
        inventory=[
            {
                "id": "ARMORY_COLANDER_HELM",
                "name": "Colander of Clear Thought",
                "item_type": "WEARABLE",
                "wearable_slots": ["Head"],
            }
        ],
        equipment={"Head": None, "Hands": None},
    )
    res = CommandParser.parse_command(avatar, "/equip Colander of Clear Thought")
    assert "[TRIGGER_EQUIP] ARMORY_COLANDER_HELM" in res
    assert avatar.equipment["Head"]["name"] == "Colander of Clear Thought"
    assert len(avatar.inventory) == 0


def test_equip_by_item_id_and_preferred_slot() -> None:
    avatar = Avatar(
        name="Tester",
        inventory=[
            {
                "id": "RUBY_RING",
                "name": "Ruby Ring",
                "item_type": "WEARABLE",
                "wearable_slots": ["Ring_1", "Ring_2"],
            }
        ],
        equipment={"Ring_1": None, "Ring_2": None},
    )
    res = CommandParser.parse_command(avatar, "/equip RUBY_RING | Ring_2")
    assert "[TRIGGER_EQUIP] RUBY_RING" in res
    assert avatar.equipment["Ring_2"]["name"] == "Ruby Ring"
    assert avatar.equipment["Ring_1"] is None


def test_unequip_by_item_name() -> None:
    avatar = Avatar(
        name="Tester",
        inventory=[],
        equipment={
            "Head": {
                "id": "HELM_01",
                "name": "Steel Helmet",
            }
        },
    )
    res = CommandParser.parse_command(avatar, "/unequip Steel Helmet")
    assert "[TRIGGER_UNEQUIP] HELM_01" in res
    assert avatar.equipment["Head"] is None
    assert len(avatar.inventory) == 1
    assert avatar.inventory[0]["name"] == "Steel Helmet"
