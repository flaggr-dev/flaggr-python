"""Shared fixtures: clients wired to an in-memory httpx transport."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Callable

import httpx
import pytest

from flaggr import AsyncFlaggrClient, FlaggrClient
from tests.support import API_KEY, API_URL, ENVIRONMENT, SERVICE_ID, Recorder


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def client(recorder: Recorder) -> Iterator[FlaggrClient]:
    with FlaggrClient(
        api_url=API_URL,
        api_key=API_KEY,
        service_id=SERVICE_ID,
        environment=ENVIRONMENT,
        transport=httpx.MockTransport(recorder),
    ) as c:
        yield c


@pytest.fixture
def make_async_client(recorder: Recorder) -> Callable[..., AsyncFlaggrClient]:
    def make(**overrides: Any) -> AsyncFlaggrClient:
        options: dict[str, Any] = {
            "api_url": API_URL,
            "api_key": API_KEY,
            "service_id": SERVICE_ID,
            "environment": ENVIRONMENT,
            "transport": httpx.MockTransport(recorder),
        }
        options.update(overrides)
        return AsyncFlaggrClient(**options)

    return make
