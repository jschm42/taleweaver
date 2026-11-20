"""Readable texts with literal backslash-n sequences get real line breaks."""

from backend.engine.world.world_generator import _normalize_text_log_content
from backend.utils.text_utils import unescape_line_breaks

ESCAPED = "QA WALKTHROUGH" + chr(92) + "n[x] Well behaves." + chr(92) + "r" + chr(92) + "n- A. Vale"


def test_literal_line_breaks_become_real_ones():
    # Act
    text = unescape_line_breaks(ESCAPED)

    # Assert
    assert text == "QA WALKTHROUGH\n[x] Well behaves.\n- A. Vale"


def test_generated_readable_text_is_normalized():
    # Act
    text = _normalize_text_log_content(ESCAPED, "", "Checklist")

    # Assert
    assert text.splitlines() == ["QA WALKTHROUGH", "[x] Well behaves.", "- A. Vale"]


def test_plain_text_is_unchanged():
    # Act / Assert
    assert unescape_line_breaks("No breaks here.") == "No breaks here."
    assert unescape_line_breaks("") == ""
