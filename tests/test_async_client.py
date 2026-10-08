"""Tests for the async client (run with asyncio.run, no plugin needed)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, Callable, TypeVar

import httpx
import pytest

from flaggr import AsyncFlaggrClient, FlaggrError, FlaggrTimeoutError, __version__
from tests.support import API_KEY, API_URL, ENVIRONMENT, SERVICE_ID, Recorder

T = TypeVar("T")
MakeClient = Callable[..., AsyncFlaggrClient]


def run(make_client: MakeClient, use: Callable[[AsyncFlaggrClient], Awaitable[T]]) -> T:
    async def main() -> T:
        async with make_client() as client:
            return await use(client)

    return asyncio.run(main())


def evaluation(value: Any, reason: str = "TARGETING_MATCH", **extra: Any) -> dict[str, Any]:
    return {"flagKey": "my-flag", "value": value, "reason": reason, **extra}


def test_posts_the_evaluation_request(make_async_client: MakeClient, recorder: Recorder) -> None:
    recorder.reply(json=evaluation(True))
    result = run(
        make_async_client,
        lambda c: c.get_boolean("my-flag", context={"targeting_key": "user-1", "plan": "pro"}),
    )

    assert result is True
    assert str(recorder.last.url) == f"{API_URL}/api/flags/evaluate"
    assert recorder.last.headers["Authorization"] == f"Bearer {API_KEY}"
    assert recorder.last.headers["User-Agent"] == f"flaggr-python/{__version__}"
    assert recorder.last_body == {
        "flagKey": "my-flag",
        "serviceId": SERVICE_ID,
        "environment": ENVIRONMENT,
        "defaultValue": False,
        "context": {"targetingKey": "user-1", "plan": "pro"},
    }


def test_defaults_to_the_evaluation_api(recorder: Recorder) -> None:
    recorder.reply(json=evaluation(True))

    async def main() -> None:
        async with AsyncFlaggrClient(
            api_key=API_KEY, service_id=SERVICE_ID, transport=httpx.MockTransport(recorder)
        ) as client:
            await client.get_boolean("my-flag")

    asyncio.run(main())
    assert str(recorder.last.url) == "https://api.flaggr.dev/api/flags/evaluate"


@pytest.mark.parametrize(
    ("method", "value", "default", "expected"),
    [
        ("get_boolean", True, False, True),
        ("get_boolean", "nope", True, True),
        ("get_string", "dark", "light", "dark"),
        ("get_string", 42, "light", "light"),
        ("get_number", 42, 0, 42),
        ("get_number", "2.5", 0, 2.5),
        ("get_number", True, 7, 7),
        ("get_object", {"a": 1}, None, {"a": 1}),
        ("get_object", "x", None, {}),
    ],
)
def test_typed_getters(
    make_async_client: MakeClient,
    recorder: Recorder,
    method: str,
    value: Any,
    default: Any,
    expected: Any,
) -> None:
    recorder.reply(json=evaluation(value))
    result = run(make_async_client, lambda c: getattr(c, method)("my-flag", default=default))
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize(
    ("method", "value"),
    [
        ("resolve_boolean", False),
        ("resolve_string", "v2"),
        ("resolve_number", 1.5),
        ("resolve_object", {"k": "v"}),
    ],
)
def test_resolvers(
    make_async_client: MakeClient, recorder: Recorder, method: str, value: Any
) -> None:
    recorder.reply(json=evaluation(value, reason="VARIANT", variant="treatment"))
    detail = run(make_async_client, lambda c: getattr(c, method)("my-flag"))

    assert detail.value == value
    assert detail.reason == "VARIANT"
    assert detail.variant == "treatment"
    assert detail.flag_key == "my-flag"
    assert detail.error_code is None


def test_flag_not_found_returns_the_default(
    make_async_client: MakeClient, recorder: Recorder
) -> None:
    recorder.reply(
        json={
            "flagKey": "missing",
            "value": None,
            "reason": "FLAG_NOT_FOUND",
            "errorCode": "FLAG_NOT_FOUND",
        }
    )
    detail = run(make_async_client, lambda c: c.resolve_string("missing", default="fallback"))

    assert detail.value == "fallback"
    assert detail.error_code == "FLAG_NOT_FOUND"


def test_http_errors_raise(make_async_client: MakeClient, recorder: Recorder) -> None:
    recorder.reply(403, json={"error": "FORBIDDEN"})
    with pytest.raises(FlaggrError, match="HTTP 403 FORBIDDEN") as caught:
        run(make_async_client, lambda c: c.get_boolean("my-flag"))
    assert caught.value.status_code == 403


def test_timeouts_raise(make_async_client: MakeClient, recorder: Recorder) -> None:
    recorder.fail(httpx.ConnectTimeout("timed out"))
    with pytest.raises(FlaggrTimeoutError):
        run(make_async_client, lambda c: c.get_number("my-flag"))


def test_network_errors_raise(make_async_client: MakeClient, recorder: Recorder) -> None:
    recorder.fail(httpx.ConnectError("connection refused"))
    with pytest.raises(FlaggrError, match="connection refused"):
        run(make_async_client, lambda c: c.get_string("my-flag"))


def test_context_manager_closes_the_client(
    make_async_client: MakeClient, recorder: Recorder
) -> None:
    recorder.reply(json=evaluation(True))
    client = make_async_client()

    async def main() -> None:
        async with client:
            await client.get_boolean("my-flag")

    asyncio.run(main())
    assert client._client.is_closed
