# Flaggr Python SDK

[![CI](https://github.com/flaggr-dev/flaggr-python/actions/workflows/ci.yml/badge.svg)](https://github.com/flaggr-dev/flaggr-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

The Python SDK for [Flaggr](https://flaggr.dev), an OpenFeature-compatible feature flag platform. It evaluates flags over Flaggr's REST API, with a sync and an async client, typed results and no dependencies beyond [httpx](https://www.python-httpx.org/).

## Installation

Requires Python 3.9 or later. The package isn't on PyPI yet, so install a release tag from GitHub:

```bash
pip install "flaggr @ git+https://github.com/flaggr-dev/flaggr-python@v0.1.0"
```

Each [release](https://github.com/flaggr-dev/flaggr-python/releases) also has the wheel and the source distribution attached. Once the package is on PyPI, `pip install flaggr` will work too.

## Quick start

```python
import os

from flaggr import FlaggrClient

client = FlaggrClient(
    api_key=os.environ["FLAGGR_API_KEY"],  # a project API token, fgr_...
    service_id=os.environ["FLAGGR_SERVICE_ID"],  # the service the flags belong to
    environment="production",
)

if client.get_boolean("checkout-v2", default=False, context={"targeting_key": "user-123"}):
    ...

client.close()
```

Create one client when your app starts and reuse it: it keeps a connection pool. `with FlaggrClient(...) as client:` closes it for you.

## Authentication

The SDK sends a [project API token](https://flaggr.dev/docs/api/tokens) as `Authorization: Bearer <token>`. Create one in your project's settings under API tokens; a token with only the read permission is enough to evaluate flags. Project tokens start with `fgr_`. Keep the token in an environment variable or a secret store, not in your code.

`service_id` is the ID of the Flaggr service that owns the flags. Flags are evaluated in the `environment` you pass (`production` unless you say otherwise).

## Evaluating flags

| Method | Returns |
| --- | --- |
| `get_boolean(key, default=False, context=None)` | `bool` |
| `get_string(key, default="", context=None)` | `str` |
| `get_number(key, default=0, context=None)` | `int` or `float` |
| `get_object(key, default=None, context=None)` | `dict` (`{}` when the default is `None`) |
| `resolve_boolean`, `resolve_string`, `resolve_number`, `resolve_object` | `EvaluationDetail` |

`default` and `context` are keyword arguments. You get `default` back when the flag doesn't exist in that service and environment, or when its value doesn't have the type you asked for.

The `resolve_*` methods return the value together with the reason the API gave for it:

```python
detail = client.resolve_string(
    "checkout-flow-version", default="v1", context={"targeting_key": "user-123"}
)

detail.value  # the value for this context, or the default
detail.reason  # "TARGETING_MATCH", "DEFAULT", "DISABLED", "VARIANT", ...
detail.variant  # the variant's name, or ""
detail.error_code  # None, "FLAG_NOT_FOUND" or "TYPE_MISMATCH"
detail.error_message  # why error_code is set
detail.metadata  # flag metadata, when the API returns any
```

## Evaluation context

The context carries the attributes your [targeting rules](https://flaggr.dev/docs/guides/targeting-rules) match against. `targeting_key` identifies the user or entity (it's sent to the API as `targetingKey`); percentage rollouts, variant splits and per-user overrides use it. Other attributes should be strings, numbers or booleans:

```python
client.get_number(
    "discount-percentage",
    default=0,
    context={
        "targeting_key": "user-456",
        "country": "AU",
        "plan": "enterprise",
        "beta_tester": True,
    },
)
```

## Async

`AsyncFlaggrClient` has the same methods, as coroutines:

```python
import asyncio
import os

from flaggr import AsyncFlaggrClient


async def main() -> None:
    async with AsyncFlaggrClient(
        api_key=os.environ["FLAGGR_API_KEY"],
        service_id=os.environ["FLAGGR_SERVICE_ID"],
    ) as client:
        theme = await client.get_string("theme-variant", default="default")
        print(theme)


asyncio.run(main())
```

## Error handling

A missing flag is not an error: you get the default, and `resolve_*` sets `error_code` to `FLAG_NOT_FOUND`. A request that fails raises `FlaggrError`: a network error, a rejected token (401 or 403), rate limiting (429) or a server error. Timeouts raise `FlaggrTimeoutError`, a subclass. `status_code` holds the HTTP status, or `None` when no response arrived.

```python
from flaggr import FlaggrError, FlaggrTimeoutError

try:
    enabled = client.get_boolean("checkout-v2", default=False)
except FlaggrTimeoutError:
    enabled = False
except FlaggrError as exc:
    print(f"Flag evaluation failed (HTTP {exc.status_code}): {exc}")
    enabled = False
```

## Configuration

| Argument | Default | Description |
| --- | --- | --- |
| `api_key` | required | A Flaggr project API token. |
| `service_id` | required | The ID of the service the flags belong to. |
| `environment` | `"production"` | The environment to evaluate in. |
| `api_url` | `"https://api.flaggr.dev"` | The Flaggr API base URL, without `/api`. |
| `timeout` | `5.0` | Seconds to wait for each request. |
| `transport` | `None` | An httpx transport, e.g. `httpx.HTTPTransport(retries=2)` (`httpx.AsyncHTTPTransport` for the async client), or `httpx.MockTransport` in your tests. |

Every evaluation is one `POST /api/flags/evaluate` request to `api_url`; the SDK doesn't cache results. `https://api.flaggr.dev` is Flaggr's evaluation API. `https://flaggr.dev` serves the same endpoint, but it only accepts string, number and boolean context values.

## OpenFeature

Flaggr also speaks the [OpenFeature Remote Evaluation Protocol](https://flaggr.dev/docs/api/ofrep). If you'd rather code against the OpenFeature API, use the OpenFeature Python SDK with its OFREP provider, as the [Python guide](https://flaggr.dev/docs/sdk/python-sdk) shows.

## Documentation

- [Flaggr docs](https://flaggr.dev/docs)
- [Python guide](https://flaggr.dev/docs/sdk/python-sdk)
- [API tokens](https://flaggr.dev/docs/api/tokens)
- [REST API reference](https://flaggr.dev/docs/api/rest-endpoints)

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check . && mypy
```

Pushing a `v*` tag builds the wheel and the source distribution and attaches them to a GitHub release.

## Security

Please report vulnerabilities to security@flaggr.dev rather than in a public issue. See [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
