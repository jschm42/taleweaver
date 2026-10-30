"""Exceptions raised by the script sandbox (re-exported by ``sandbox``)."""


class ScriptSecurityError(Exception):
    """Raised when a script attempts an unauthorized or unsafe operation."""

    pass


class ScriptExecutionError(Exception):
    """Raised when a runtime error occurs during script evaluation."""

    pass


class ScriptTimeoutError(ScriptExecutionError):
    """Raised when a script exceeds its maximum execution instruction budget."""

    pass
