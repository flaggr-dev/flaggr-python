"""Type definitions for the Flaggr SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Optional, TypeVar, Union

FlagValue = Union[bool, str, int, float, dict[str, Any]]
"""A value a flag can resolve to."""

EvaluationContext = dict[str, Any]
"""Attributes that targeting rules evaluate against.

Use ``targeting_key`` (or ``targetingKey``) for the user or entity ID. Other
values should be strings, numbers or booleans.
"""

T = TypeVar("T")


class EvaluationReason(str, Enum):
    """Reasons the Flaggr API reports for an evaluation.

    ``EvaluationDetail.reason`` is a plain string; compare it with these members
    (``detail.reason == EvaluationReason.TARGETING_MATCH``).
    """

    DEFAULT = "DEFAULT"
    TARGETING_MATCH = "TARGETING_MATCH"
    VARIANT = "VARIANT"
    SPLIT = "SPLIT"
    EXPERIMENT = "EXPERIMENT"
    OVERRIDE = "OVERRIDE"
    DISABLED = "DISABLED"
    PREREQUISITE_FAILED = "PREREQUISITE_FAILED"
    MUTUAL_EXCLUSION = "MUTUAL_EXCLUSION"
    STATIC = "STATIC"
    CACHED = "CACHED"
    NOT_FOUND = "NOT_FOUND"
    FLAG_NOT_FOUND = "FLAG_NOT_FOUND"
    ERROR = "ERROR"


class ErrorCode(str, Enum):
    """Error codes set on ``EvaluationDetail.error_code``."""

    FLAG_NOT_FOUND = "FLAG_NOT_FOUND"
    TYPE_MISMATCH = "TYPE_MISMATCH"


@dataclass
class EvaluationDetail(Generic[T]):
    """An evaluation result with the reason, variant and any error.

    When the flag doesn't exist (``error_code == "FLAG_NOT_FOUND"``) or its value
    doesn't have the requested type (``error_code == "TYPE_MISMATCH"``),
    ``value`` is the default you passed.
    """

    value: T
    reason: str = ""
    variant: str = ""
    flag_key: str = ""
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
