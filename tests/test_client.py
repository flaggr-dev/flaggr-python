"""Tests for the synchronous client."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from flaggr import (
    DEFAULT_API_URL,
    EvaluationReason,
    FlaggrClient,
    FlaggrError,
    FlaggrTimeoutError,
    __version__,
)
from tests.support import API_KEY, API_URL, ENVIRONMENT, SERVICE_ID, Recorder


def evaluation(value: Any, reason: str = "TARGETING_MATCH", **extra: Any) -> dict[str, Any]:
    return {"flagKey": "my-flag", "value": value, "reason": reason, **extra}


class TestRequest:
    def test_posts_the_evaluation_body(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(json=evaluation(True))
        client.get_boolean("my-flag", default=False)

        assert recorder.last.method == "POST"
        assert str(recorder.last.url) == f"{API_URL}/api/flags/evaluate"
        assert recorder.last_body == {
            "flagKey": "my-flag",
            "serviceId": SERVICE_ID,
            "environment": ENVIRONMENT,
            "defaultValue": False,
        }

    def test_sends_the_context_with_a_camel_case_targeting_key(
        self, client: FlaggrClient, recorder: Recorder
    ) -> None:
        recorder.reply(json=evaluation(True))
        client.get_boolean(
            "my-flag",
            context={"targeting_key": "user-123", "plan": "enterprise", "seats": 5, "beta": True},
        )

        assert recorder.last_body["context"] == {
            "targetingKey": "user-123",
            "plan": "enterprise",
            "seats": 5,
            "beta": True,
        }

    def test_sends_the_token_and_identifies_the_sdk(
        self, client: FlaggrClient, recorder: Recorder
    ) -> None:
        recorder.reply(json=evaluation("dark"))
        client.get_string("theme")

        headers = recorder.last.headers
        assert headers["Authorization"] == f"Bearer {API_KEY}"
        assert headers["User-Agent"] == f"flaggr-python/{__version__}"
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"

    def test_defaults_to_the_evaluation_api(self, recorder: Recorder) -> None:
        recorder.reply(json=evaluation(True))
        with FlaggrClient(
            api_key=API_KEY, service_id=SERVICE_ID, transport=httpx.MockTransport(recorder)
        ) as client:
            client.get_boolean("my-flag")

        assert DEFAULT_API_URL == "https://api.flaggr.dev"
        assert str(recorder.last.url) == "https://api.flaggr.dev/api/flags/evaluate"
        assert recorder.last_body["environment"] == "production"

    def test_strips_a_trailing_slash_and_token_whitespace(self, recorder: Recorder) -> None:
        recorder.reply(json=evaluation(True))
        with FlaggrClient(
            api_url="https://flaggr.test/",
            api_key=f"  {API_KEY}\n",
            service_id=SERVICE_ID,
            transport=httpx.MockTransport(recorder),
        ) as client:
            client.get_boolean("my-flag")

        assert str(recorder.last.url) == "https://flaggr.test/api/flags/evaluate"
        assert recorder.last.headers["Authorization"] == f"Bearer {API_KEY}"

    @pytest.mark.parametrize(
        ("api_key", "service_id"), [("", SERVICE_ID), ("   ", SERVICE_ID), (API_KEY, "")]
    )
    def test_requires_a_token_and_a_service(self, api_key: str, service_id: str) -> None:
        with pytest.raises(ValueError):
            FlaggrClient(api_key=api_key, service_id=service_id)


class TestGetBoolean:
    @pytest.mark.parametrize("value", [True, False])
    def test_returns_the_value(self, client: FlaggrClient, recorder: Recorder, value: bool) -> None:
        recorder.reply(json=evaluation(value))
        assert client.get_boolean("my-flag", default=not value) is value

    @pytest.mark.parametrize(("value", "expected"), [("true", True), ("FALSE", False)])
    def test_reads_boolean_strings(
        self, client: FlaggrClient, recorder: Recorder, value: str, expected: bool
    ) -> None:
        recorder.reply(json=evaluation(value))
        assert client.get_boolean("my-flag", default=not expected) is expected

    @pytest.mark.parametrize("value", ["yes", 1, {"on": True}])
    def test_returns_the_default_for_other_types(
        self, client: FlaggrClient, recorder: Recorder, value: Any
    ) -> None:
        recorder.reply(json=evaluation(value))
        assert client.get_boolean("my-flag", default=True) is True


class TestGetString:
    def test_returns_the_value(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(json=evaluation("dark"))
        assert client.get_string("theme", default="light") == "dark"

    @pytest.mark.parametrize("value", [True, 42, {"a": 1}])
    def test_returns_the_default_for_other_types(
        self, client: FlaggrClient, recorder: Recorder, value: Any
    ) -> None:
        recorder.reply(json=evaluation(value))
        assert client.get_string("theme", default="light") == "light"


class TestGetNumber:
    @pytest.mark.parametrize("value", [42, 2.5, 0])
    def test_returns_the_value(self, client: FlaggrClient, recorder: Recorder, value: Any) -> None:
        recorder.reply(json=evaluation(value))
        assert client.get_number("limit", default=10) == value

    @pytest.mark.parametrize(("value", "expected"), [("42", 42), ("3.14", 3.14)])
    def test_reads_numeric_strings(
        self, client: FlaggrClient, recorder: Recorder, value: str, expected: float
    ) -> None:
        recorder.reply(json=evaluation(value))
        assert client.get_number("rate", default=1) == expected

    @pytest.mark.parametrize("value", [True, "fast", "nan", {"a": 1}])
    def test_returns_the_default_for_other_types(
        self, client: FlaggrClient, recorder: Recorder, value: Any
    ) -> None:
        recorder.reply(json=evaluation(value))
        assert client.get_number("limit", default=10) == 10


class TestGetObject:
    def test_returns_the_value(self, client: FlaggrClient, recorder: Recorder) -> None:
        banner = {"text": "hello", "color": "blue"}
        recorder.reply(json=evaluation(banner))
        assert client.get_object("banner") == banner
        assert recorder.last_body["defaultValue"] == {}

    def test_returns_the_default_for_other_types(
        self, client: FlaggrClient, recorder: Recorder
    ) -> None:
        recorder.reply(json=evaluation("not an object"))
        assert client.get_object("banner", default={"text": "hi"}) == {"text": "hi"}
        assert client.get_object("banner") == {}


class TestResolve:
    def test_returns_the_details(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(
            json=evaluation(
                "v2",
                reason="EXPERIMENT",
                variant="treatment",
                flagMetadata={"experimentId": "exp-1"},
                traceId="abc",
            )
        )
        detail = client.resolve_string("checkout", default="v1")

        assert detail.value == "v2"
        assert detail.reason == EvaluationReason.EXPERIMENT
        assert detail.variant == "treatment"
        assert detail.flag_key == "checkout"
        assert detail.error_code is None
        assert detail.error_message is None
        assert detail.metadata == {"experimentId": "exp-1"}

    def test_resolves_every_type(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(json=evaluation(True))
        assert client.resolve_boolean("f").value is True
        recorder.reply(json=evaluation(7))
        assert client.resolve_number("f").value == 7
        recorder.reply(json=evaluation({"k": "v"}))
        assert client.resolve_object("f").value == {"k": "v"}

    def test_a_missing_variant_is_an_empty_string(
        self, client: FlaggrClient, recorder: Recorder
    ) -> None:
        recorder.reply(json=evaluation(False, reason="DEFAULT"))
        detail = client.resolve_boolean("my-flag")
        assert detail.variant == ""
        assert detail.metadata == {}

    def test_flag_not_found_from_the_control_plane(
        self, client: FlaggrClient, recorder: Recorder
    ) -> None:
        # https://flaggr.dev echoes the default back with reason NOT_FOUND.
        recorder.reply(json={"flagKey": "missing", "value": True, "reason": "NOT_FOUND"})
        detail = client.resolve_boolean("missing", default=True)

        assert detail.value is True
        assert detail.reason == "NOT_FOUND"
        assert detail.error_code == "FLAG_NOT_FOUND"
        assert detail.error_message == "Flag not found"

    def test_flag_not_found_from_the_data_plane(
        self, client: FlaggrClient, recorder: Recorder
    ) -> None:
        # https://api.flaggr.dev answers value: null with an error code.
        recorder.reply(
            json={
                "flagKey": "missing",
                "value": None,
                "reason": "FLAG_NOT_FOUND",
                "errorCode": "FLAG_NOT_FOUND",
                "errorMessage": "Flag not found",
                "evaluatedAt": "2026-10-08T00:00:00Z",
            }
        )
        detail = client.resolve_number("missing", default=3)

        assert detail.value == 3
        assert detail.reason == "FLAG_NOT_FOUND"
        assert detail.error_code == "FLAG_NOT_FOUND"
        assert client.get_number("missing", default=3) == 3
        assert client.get_string("missing", default="x") == "x"
        assert client.get_boolean("missing", default=True) is True
        assert client.get_object("missing", default={"a": 1}) == {"a": 1}

    def test_a_type_mismatch_returns_the_default(
        self, client: FlaggrClient, recorder: Recorder
    ) -> None:
        recorder.reply(json=evaluation("Welcome!", reason="DEFAULT"))
        detail = client.resolve_boolean("announcement", default=True)

        assert detail.value is True
        assert detail.reason == EvaluationReason.ERROR
        assert detail.error_code == "TYPE_MISMATCH"
        assert detail.error_message == "Expected a boolean value, got str"


class TestErrors:
    def test_rejected_token(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(401, json={"error": "UNAUTHENTICATED"})
        with pytest.raises(FlaggrError, match="HTTP 401 UNAUTHENTICATED") as caught:
            client.get_boolean("my-flag")
        assert caught.value.status_code == 401

    def test_error_and_message(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(403, json={"error": "Forbidden", "message": "Invalid API token"})
        with pytest.raises(FlaggrError, match="HTTP 403 Forbidden: Invalid API token"):
            client.resolve_boolean("my-flag")

    def test_rate_limited(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(429, json={"error": "Too Many Requests"}, headers={"Retry-After": "1"})
        with pytest.raises(FlaggrError) as caught:
            client.get_number("my-flag")
        assert caught.value.status_code == 429

    def test_not_found_points_at_api_url(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(404, text="404 page not found")
        with pytest.raises(FlaggrError, match="check api_url") as caught:
            client.get_boolean("my-flag")
        assert caught.value.status_code == 404
        assert f"{API_URL}/api/flags/evaluate" in str(caught.value)

    def test_server_error_with_a_text_body(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.reply(502, text="Bad Gateway")
        with pytest.raises(FlaggrError, match="HTTP 502 Bad Gateway") as caught:
            client.get_string("my-flag")
        assert caught.value.status_code == 502

    @pytest.mark.parametrize("body", [b"<html>oops</html>", b"[1, 2]"])
    def test_unexpected_success_body(
        self, client: FlaggrClient, recorder: Recorder, body: bytes
    ) -> None:
        recorder.reply(200, content=body)
        with pytest.raises(FlaggrError, match="Evaluation failed"):
            client.get_boolean("my-flag")

    def test_timeout(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.fail(httpx.ReadTimeout("timed out"))
        with pytest.raises(FlaggrTimeoutError) as caught:
            client.get_boolean("my-flag")
        assert caught.value.status_code is None

    def test_network_error(self, client: FlaggrClient, recorder: Recorder) -> None:
        recorder.fail(httpx.ConnectError("connection refused"))
        with pytest.raises(FlaggrError, match="connection refused") as caught:
            client.get_boolean("my-flag")
        assert not isinstance(caught.value, FlaggrTimeoutError)
        assert caught.value.status_code is None


def test_context_manager_closes_the_client(recorder: Recorder) -> None:
    recorder.reply(json=evaluation(True))
    with FlaggrClient(
        api_url=API_URL,
        api_key=API_KEY,
        service_id=SERVICE_ID,
        transport=httpx.MockTransport(recorder),
    ) as client:
        assert client.get_boolean("flag") is True
    assert client._client.is_closed
