"""Synchronous Flaggr client."""

from __future__ import annotations

from typing import Any, Optional, Union

import httpx

from flaggr._core import (
    DEFAULT_API_URL,
    EVALUATE_PATH,
    as_bool,
    as_number,
    as_object,
    as_str,
    build_payload,
    check_settings,
    http_options,
    parse_response,
    to_detail,
    transport_error,
)
from flaggr.types import EvaluationContext, EvaluationDetail, FlagValue


class FlaggrClient:
    """Evaluates Flaggr feature flags over HTTP.

    Each evaluation is one ``POST /api/flags/evaluate`` request. Reuse one client
    (it keeps a connection pool) and close it when you're done, or use it as a
    context manager.

    Example::

        from flaggr import FlaggrClient

        with FlaggrClient(api_key="fgr_...", service_id="web-app") as client:
            enabled = client.get_boolean(
                "checkout-v2", default=False, context={"targeting_key": "user-123"}
            )

    Args:
        api_key: A Flaggr API token. A read-only project token is enough.
        service_id: The ID of the service the flags belong to.
        api_url: The Flaggr API base URL, without ``/api``.
        environment: The environment to evaluate in.
        timeout: Seconds to wait for each request.
        transport: An httpx transport to send requests with, such as
            ``httpx.HTTPTransport(retries=2)``, or ``httpx.MockTransport`` in tests.

    Raises:
        ValueError: If ``api_key`` or ``service_id`` is empty.
    """

    def __init__(
        self,
        *,
        api_key: str,
        service_id: str,
        api_url: str = DEFAULT_API_URL,
        environment: str = "production",
        timeout: float = 5.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        key = check_settings(api_key, service_id)
        self._api_url = api_url.rstrip("/")
        self._service_id = service_id
        self._environment = environment
        self._client = httpx.Client(
            transport=transport, **http_options(self._api_url, key, timeout)
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> FlaggrClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # -- Values --

    def get_boolean(
        self,
        flag_key: str,
        *,
        default: bool = False,
        context: Optional[EvaluationContext] = None,
    ) -> bool:
        """Evaluate a boolean flag. Returns ``default`` if the flag doesn't exist."""
        return self.resolve_boolean(flag_key, default=default, context=context).value

    def get_string(
        self,
        flag_key: str,
        *,
        default: str = "",
        context: Optional[EvaluationContext] = None,
    ) -> str:
        """Evaluate a string flag. Returns ``default`` if the flag doesn't exist."""
        return self.resolve_string(flag_key, default=default, context=context).value

    def get_number(
        self,
        flag_key: str,
        *,
        default: Union[int, float] = 0,
        context: Optional[EvaluationContext] = None,
    ) -> Union[int, float]:
        """Evaluate a number flag. Returns ``default`` if the flag doesn't exist."""
        return self.resolve_number(flag_key, default=default, context=context).value

    def get_object(
        self,
        flag_key: str,
        *,
        default: Optional[dict[str, Any]] = None,
        context: Optional[EvaluationContext] = None,
    ) -> dict[str, Any]:
        """Evaluate an object (JSON) flag. Returns ``default`` (or ``{}``) if it doesn't exist."""
        return self.resolve_object(flag_key, default=default, context=context).value

    # -- Details --

    def resolve_boolean(
        self,
        flag_key: str,
        *,
        default: bool = False,
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[bool]:
        """Evaluate a boolean flag and return the value with its reason and variant."""
        data = self._evaluate(flag_key, default, context)
        return to_detail(flag_key, default, data, as_bool, "boolean")

    def resolve_string(
        self,
        flag_key: str,
        *,
        default: str = "",
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[str]:
        """Evaluate a string flag and return the value with its reason and variant."""
        data = self._evaluate(flag_key, default, context)
        return to_detail(flag_key, default, data, as_str, "string")

    def resolve_number(
        self,
        flag_key: str,
        *,
        default: Union[int, float] = 0,
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[Union[int, float]]:
        """Evaluate a number flag and return the value with its reason and variant."""
        data = self._evaluate(flag_key, default, context)
        return to_detail(flag_key, default, data, as_number, "number")

    def resolve_object(
        self,
        flag_key: str,
        *,
        default: Optional[dict[str, Any]] = None,
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[dict[str, Any]]:
        """Evaluate an object (JSON) flag and return the value with its reason and variant."""
        fallback: dict[str, Any] = default if default is not None else {}
        data = self._evaluate(flag_key, fallback, context)
        return to_detail(flag_key, fallback, data, as_object, "object")

    # -- Internal --

    def _evaluate(
        self,
        flag_key: str,
        default_value: FlagValue,
        context: Optional[EvaluationContext],
    ) -> dict[str, Any]:
        payload = build_payload(
            flag_key, self._service_id, self._environment, default_value, context
        )
        try:
            response = self._client.post(EVALUATE_PATH, json=payload)
        except httpx.HTTPError as exc:
            raise transport_error(exc) from exc
        return parse_response(response)
