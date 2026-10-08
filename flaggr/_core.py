"""Request building and response handling shared by the sync and async clients."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Callable, Optional, TypeVar, Union

import httpx

from flaggr._version import __version__
from flaggr.errors import FlaggrError, FlaggrTimeoutError
from flaggr.types import (
    ErrorCode,
    EvaluationContext,
    EvaluationDetail,
    EvaluationReason,
    FlagValue,
)

DEFAULT_API_URL = "https://api.flaggr.dev"
"""Flaggr's evaluation API (the data plane)."""

EVALUATE_PATH = "/api/flags/evaluate"
USER_AGENT = f"flaggr-python/{__version__}"

T = TypeVar("T")
Number = Union[int, float]

_NOT_FOUND_REASONS = {EvaluationReason.NOT_FOUND.value, EvaluationReason.FLAG_NOT_FOUND.value}


def check_settings(api_key: str, service_id: str, environment: str) -> tuple[str, str, str]:
    """Validate the client settings and return them without surrounding whitespace.

    Values read from environment variables often end with a newline, which the
    API would reject.
    """
    key = api_key.strip() if isinstance(api_key, str) else ""
    if not key:
        raise ValueError("api_key is required: a Flaggr API token")
    service = service_id.strip() if isinstance(service_id, str) else ""
    if not service:
        raise ValueError("service_id is required: the ID of the service the flags belong to")
    env = environment.strip() if isinstance(environment, str) else ""
    if not env:
        raise ValueError('environment must not be empty (the default is "production")')
    return key, service, env


def http_options(api_url: str, api_key: str, timeout: float) -> dict[str, Any]:
    """Keyword arguments for ``httpx.Client`` / ``httpx.AsyncClient``."""
    return {
        "base_url": api_url.rstrip("/"),
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        "timeout": timeout,
    }


def build_payload(
    flag_key: str,
    service_id: str,
    environment: str,
    default_value: FlagValue,
    context: Optional[EvaluationContext],
) -> dict[str, Any]:
    """The JSON body for ``POST /api/flags/evaluate``."""
    payload: dict[str, Any] = {
        "flagKey": flag_key,
        "serviceId": service_id,
        "environment": environment,
        "defaultValue": default_value,
    }
    sent: dict[str, Any] = {}
    for name, value in (context or {}).items():
        if value is None:
            # An attribute set to None is left out, as if it weren't set:
            # https://flaggr.dev rejects null attribute values.
            continue
        if name in ("targeting_key", "targetingKey"):
            # The API names the targeting key in camelCase, and
            # https://api.flaggr.dev ignores a targeting key that isn't a string.
            sent["targetingKey"] = value if isinstance(value, str) else str(value)
        else:
            sent[name] = value
    if sent:
        payload["context"] = sent
    return payload


def transport_error(exc: httpx.HTTPError) -> FlaggrError:
    """Translate an httpx error raised before a response arrived."""
    if isinstance(exc, httpx.TimeoutException):
        return FlaggrTimeoutError()
    return FlaggrError(f"HTTP error: {exc}")


def parse_response(response: httpx.Response) -> dict[str, Any]:
    """Return the JSON body of a successful evaluation, or raise ``FlaggrError``."""
    if response.status_code != 200:
        raise FlaggrError(_error_message(response), status_code=response.status_code)
    try:
        data = response.json()
    except ValueError as exc:
        raise FlaggrError(
            "Evaluation failed: the response is not JSON", status_code=response.status_code
        ) from exc
    if not isinstance(data, dict):
        raise FlaggrError(
            "Evaluation failed: unexpected response body", status_code=response.status_code
        )
    return data


def _error_message(response: httpx.Response) -> str:
    message = f"Evaluation failed: HTTP {response.status_code}"
    if response.has_redirect_location:
        return message + _redirect_hint(response.headers["location"])
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        detail = ": ".join(str(body[key]) for key in ("error", "message") if body.get(key))
    if not detail and "html" not in response.headers.get("content-type", "").lower():
        # A text body, on one line. An HTML error page would only add noise.
        detail = " ".join(response.text.split())[:200]
    if detail:
        message += f" {detail}"
    if response.status_code == 404:
        message += f" (no evaluation endpoint at {_request_url(response)}; check api_url)"
    return message


def _redirect_hint(location: str) -> str:
    # The SDK doesn't follow redirects (a 301 or 302 would turn the POST into a
    # GET), so it names the address the server points to instead.
    if "://" in location and location.endswith(EVALUATE_PATH):
        return f" (redirected: set api_url to {location[: -len(EVALUATE_PATH)]})"
    return f" (redirected to {location}; check api_url)"


def _request_url(response: httpx.Response) -> str:
    try:
        return str(response.request.url)
    except RuntimeError:  # a response built without a request
        return EVALUATE_PATH


# -- Type coercion: each returns None when the value doesn't have the type --


def as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "false"):
            return lowered == "true"
    return None


def as_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def as_number(value: Any) -> Optional[Number]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            pass
        try:
            number = float(text)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def as_object(value: Any) -> Optional[dict[str, Any]]:
    return value if isinstance(value, dict) else None


def to_detail(
    flag_key: str,
    default: T,
    data: Mapping[str, Any],
    coerce: Callable[[Any], Optional[T]],
    type_name: str,
) -> EvaluationDetail[T]:
    """Build an ``EvaluationDetail`` from an API response.

    The value falls back to ``default`` when the flag doesn't exist (the
    control plane answers ``reason: NOT_FOUND`` with the default, the data
    plane ``reason: FLAG_NOT_FOUND`` with ``value: null``) or when the value
    doesn't have the requested type.
    """
    reason = str(data.get("reason") or "")
    variant = data.get("variant")
    error_code = data.get("errorCode") or None
    error_message = data.get("errorMessage") or None
    metadata = data.get("flagMetadata") or data.get("metadata") or {}

    if reason in _NOT_FOUND_REASONS and error_code is None:
        error_code = ErrorCode.FLAG_NOT_FOUND.value
        error_message = error_message or "Flag not found"

    raw = data.get("value")
    value: T = default
    if raw is not None:
        coerced = coerce(raw)
        if coerced is not None:
            value = coerced
        elif error_code is None:
            reason = EvaluationReason.ERROR.value
            error_code = ErrorCode.TYPE_MISMATCH.value
            article = "an" if type_name[:1] in "aeiou" else "a"
            error_message = f"Expected {article} {type_name} value, got {type(raw).__name__}"

    return EvaluationDetail(
        value=value,
        reason=reason,
        variant=variant if isinstance(variant, str) else "",
        flag_key=flag_key,
        error_code=str(error_code) if error_code is not None else None,
        error_message=str(error_message) if error_message is not None else None,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )
