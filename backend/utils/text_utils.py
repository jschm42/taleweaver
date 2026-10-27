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
