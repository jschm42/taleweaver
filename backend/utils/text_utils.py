import random
import re
import string

import uuid6


def slugify(text: str) -> str:
    """
    Converts a string to a URL-friendly slug.
    Example: "The Lost Cave!" -> "the-lost-cave"
    """
    if not text:
        return "untitled"
    # Convert to lowercase and remove non-word characters (except spaces/hyphens)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_-]+", "-", text)
    # Trim hyphens from ends
    return text.strip("-")


_ESCAPED_BREAKS = re.compile(r"\\r\\n|\\n|\\r")


def unescape_line_breaks(text: str) -> str:
    """Turns literal ``\\n`` sequences (double-escaped LLM / JSON output) into real line breaks.

    Readable texts sometimes arrive with the two characters backslash + ``n`` instead of a
    newline, which the client then shows verbatim.
    """
    if not text or "\\" not in text:
        return text or ""
    return _ESCAPED_BREAKS.sub("\n", text)


def generate_short_id(length: int = 8) -> str:
    """
    Generates a short alphanumeric ID.
    """
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def generate_adventure_id(title: str = "") -> str:
    """Return a title-independent UUID; retain the argument for existing callers."""
    return str(uuid6.uuid7())


def generate_session_id(title: str = "") -> str:
    """Return a title-independent UUID; existing save IDs are never rewritten."""
    return str(uuid6.uuid7())
