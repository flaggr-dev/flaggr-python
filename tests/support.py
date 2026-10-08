"""Test helpers: constants and a recording ``httpx.MockTransport`` handler."""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx

API_URL = "https://flaggr.test"
API_KEY = "fgr_test_token"
SERVICE_ID = "test-service"
ENVIRONMENT = "staging"


class Recorder:
    """A ``httpx.MockTransport`` handler: records requests, answers with a canned response."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._respond: Callable[[httpx.Request], httpx.Response] = lambda _: httpx.Response(
            200, json={}
        )

    def reply(self, status_code: int = 200, **kwargs: Any) -> None:
        """Answer every request with this response (``json=``, ``text=``, ``content=``)."""
        self._respond = lambda request: httpx.Response(status_code, request=request, **kwargs)

    def fail(self, exc: Exception) -> None:
        """Raise ``exc`` instead of answering."""

        def respond(request: httpx.Request) -> httpx.Response:
            raise exc

        self._respond = respond

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._respond(request)

    @property
    def last(self) -> httpx.Request:
        assert self.requests, "no request was sent"
        return self.requests[-1]

    @property
    def last_body(self) -> dict[str, Any]:
        body: dict[str, Any] = json.loads(self.last.content)
        return body
