"""Package-level checks: exports, version and runtime type hints."""

from __future__ import annotations

import typing
from importlib.metadata import version

import flaggr
from flaggr import EvaluationDetail, FlaggrClient


def test_exports() -> None:
    for name in flaggr.__all__:
        assert hasattr(flaggr, name), name


def test_version_matches_the_installed_distribution() -> None:
    assert flaggr.__version__ == version("flaggr")


def test_type_hints_evaluate_on_every_supported_python() -> None:
    # Tools such as pydantic call get_type_hints; Python 3.9 can't evaluate `X | None`.
    hints = typing.get_type_hints(EvaluationDetail)
    assert hints["error_code"] == typing.Optional[str]
    typing.get_type_hints(FlaggrClient.resolve_number)
    typing.get_type_hints(FlaggrClient.__init__)
