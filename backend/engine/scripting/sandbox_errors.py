"""Exceptions raised by the script sandbox (re-exported by ``sandbox``)."""

import difflib
from typing import Any


class ScriptSecurityError(Exception):
    """Raised when a script attempts an unauthorized or unsafe operation."""

    pass


class ScriptExecutionError(Exception):
    """Raised when a runtime error occurs during script evaluation."""

    pass


class ScriptTimeoutError(ScriptExecutionError):
    """Raised when a script exceeds its maximum execution instruction budget."""

    pass


def attribute_error_message(obj: Any, attr: str, exc: AttributeError) -> str:
    """The AttributeError text plus the closest public name, e.g. ``tw.award`` -> ``awards``."""
    names = [name for name in dir(obj) if not name.startswith("_")]
    match = difflib.get_close_matches(attr, names, n=1, cutoff=0.6)
    hint = f" Did you mean '{match[0]}'?" if match else ""
    return f"AttributeError: {exc}.{hint}"
