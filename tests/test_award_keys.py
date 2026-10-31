"""Award keys: upper case for new awards, case-insensitive matching when granting."""

from backend.engine.rules.award_keys import (
    canonical_award_keys,
    normalize_award_key,
    normalize_new_award_keys,
)


def test_normalize_award_key_upper_cases_and_joins_words():
    # Act / Assert
    assert normalize_award_key("award_brass_lever_whisperer") == "AWARD_BRASS_LEVER_WHISPERER"
    assert normalize_award_key(" brass lever-whisperer ") == "BRASS_LEVER_WHISPERER"
    assert normalize_award_key(None) == ""


def test_new_award_keys_are_upper_cased_in_place():
    # Arrange
    awards = [{"key": "award_brass_lever"}, {"key": ""}, "not a dict"]

    # Act
    normalize_new_award_keys(awards)

    # Assert
    assert awards[0]["key"] == "AWARD_BRASS_LEVER"
    assert awards[1]["key"] == ""


def test_requested_keys_map_to_stored_keys_ignoring_case():
    # Arrange: an older adventure still stores a lower-case key
    awards = [{"key": "award_brass_lever"}, {"key": "SLAYER_OF_RATS"}]

    # Act
    keys = canonical_award_keys(["AWARD_BRASS_LEVER", "slayer_of_rats", "UNKNOWN", ""], awards)

    # Assert: stored spelling wins, unknown keys are kept for the "non-existent" warning
    assert keys == ["award_brass_lever", "SLAYER_OF_RATS", "UNKNOWN"]
