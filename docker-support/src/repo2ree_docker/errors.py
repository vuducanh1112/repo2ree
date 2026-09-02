"""Docker runtime failure types shared across process boundaries."""


class WorkbenchGoneError(RuntimeError):
    """The allocated Docker environment is gone or stopping."""
