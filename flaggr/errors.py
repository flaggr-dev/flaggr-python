"""Exception types for the Flaggr SDK."""

from __future__ import annotations

from typing import Optional


class FlaggrError(Exception):
    """Raised when an evaluation request fails.

    ``status_code`` is the HTTP status the API answered with, or ``None`` when
    the request didn't get a response (a network error or a timeout).
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FlaggrTimeoutError(FlaggrError):
    """Raised when a request to the Flaggr API times out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message)
