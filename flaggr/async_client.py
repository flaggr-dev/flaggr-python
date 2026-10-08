"""Async Flaggr client."""

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


class AsyncFlaggrClient:
    """Evaluates Flaggr feature flags over HTTP with ``asyncio``.

    The same API as :class:`flaggr.FlaggrClient`, with ``await``.

    Example::

        from flaggr import AsyncFlaggrClient

        async with AsyncFlaggrClient(api_key="fgr_...", service_id="web-app") as client:
            enabled = await client.get_boolean("checkout-v2", default=False)

    Args:
        api_key: A Flaggr API token. A read-only project token is enough.
        service_id: The ID of the service the flags belong to.
        api_url: The Flaggr API base URL, without ``/api``.
        environment: The environment to evaluate in.
        timeout: Seconds to wait for each request.
        transport: An httpx async transport to send requests with, such as
            ``httpx.AsyncHTTPTransport(retries=2)``, or ``httpx.MockTransport`` in tests.

    Raises:
        ValueError: If ``api_key``, ``service_id`` or ``environment`` is empty.
    """

    def __init__(
        self,
        *,
        api_key: str,
        service_id: str,
        api_url: str = DEFAULT_API_URL,
        environment: str = "production",
        timeout: float = 5.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        key, self._service_id, self._environment = check_settings(api_key, service_id, environment)
        self._api_url = api_url.rstrip("/")
        self._client = httpx.AsyncClient(
            transport=transport, **http_options(self._api_url, key, timeout)
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncFlaggrClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # -- Values --

    async def get_boolean(
        self,
        flag_key: str,
        *,
        default: bool = False,
        context: Optional[EvaluationContext] = None,
    ) -> bool:
        """Evaluate a boolean flag. Returns ``default`` if the flag doesn't exist."""
        detail = await self.resolve_boolean(flag_key, default=default, context=context)
        return detail.value

    async def get_string(
        self,
        flag_key: str,
        *,
        default: str = "",
        context: Optional[EvaluationContext] = None,
    ) -> str:
        """Evaluate a string flag. Returns ``default`` if the flag doesn't exist."""
        detail = await self.resolve_string(flag_key, default=default, context=context)
        return detail.value

    async def get_number(
        self,
        flag_key: str,
        *,
        default: Union[int, float] = 0,
        context: Optional[EvaluationContext] = None,
    ) -> Union[int, float]:
        """Evaluate a number flag. Returns ``default`` if the flag doesn't exist."""
        detail = await self.resolve_number(flag_key, default=default, context=context)
        return detail.value

    async def get_object(
        self,
        flag_key: str,
        *,
        default: Optional[dict[str, Any]] = None,
        context: Optional[EvaluationContext] = None,
    ) -> dict[str, Any]:
        """Evaluate an object (JSON) flag. Returns ``default`` (or ``{}``) if it doesn't exist."""
        detail = await self.resolve_object(flag_key, default=default, context=context)
        return detail.value

    # -- Details --

    async def resolve_boolean(
        self,
        flag_key: str,
        *,
        default: bool = False,
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[bool]:
        """Evaluate a boolean flag and return the value with its reason and variant."""
        data = await self._evaluate(flag_key, default, context)
        return to_detail(flag_key, default, data, as_bool, "boolean")

    async def resolve_string(
        self,
        flag_key: str,
        *,
        default: str = "",
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[str]:
        """Evaluate a string flag and return the value with its reason and variant."""
        data = await self._evaluate(flag_key, default, context)
        return to_detail(flag_key, default, data, as_str, "string")

    async def resolve_number(
        self,
        flag_key: str,
        *,
        default: Union[int, float] = 0,
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[Union[int, float]]:
        """Evaluate a number flag and return the value with its reason and variant."""
        data = await self._evaluate(flag_key, default, context)
        return to_detail(flag_key, default, data, as_number, "number")

    async def resolve_object(
        self,
        flag_key: str,
        *,
        default: Optional[dict[str, Any]] = None,
        context: Optional[EvaluationContext] = None,
    ) -> EvaluationDetail[dict[str, Any]]:
        """Evaluate an object (JSON) flag and return the value with its reason and variant."""
        fallback: dict[str, Any] = default if default is not None else {}
        data = await self._evaluate(flag_key, fallback, context)
        return to_detail(flag_key, fallback, data, as_object, "object")

    # -- Internal --

    async def _evaluate(
        self,
        flag_key: str,
        default_value: FlagValue,
        context: Optional[EvaluationContext],
    ) -> dict[str, Any]:
        payload = build_payload(
            flag_key, self._service_id, self._environment, default_value, context
        )
        try:
            response = await self._client.post(EVALUATE_PATH, json=payload)
        except httpx.HTTPError as exc:
            raise transport_error(exc) from exc
        return parse_response(response)
