"""Immutable internal structures, constructed only after JSON validation."""

from dataclasses import asdict, dataclass
from enum import StrEnum
from fractions import Fraction

from .diagnostics import ErrorCode


class Classification(StrEnum):
    D = "D"
    K = "K"
    S = "S"
    U = "U"


class SatState(StrEnum):
    SAT = "sat"
    UNSAT = "unsat"


@dataclass(frozen=True)
class Allowed:
    # Numeric bounds are exact rationals in the canonical dimension unit.
    kind: str
    members: frozenset[bool | str] = frozenset()
    lower: Fraction | None = None
    upper: Fraction | None = None


@dataclass(frozen=True)
class Domain:
    values: Allowed
    dimension: str | None = None


@dataclass(frozen=True)
class SubjectModel:
    object_id: str
    parameter_id: str
    situations: tuple[str, ...]
    domain: Domain


@dataclass(frozen=True)
class Expectation:
    object_id: str
    parameter_id: str
    basis: str
    conditions: frozenset[str] | None
    values: Allowed | None


@dataclass(frozen=True)
class Completion:
    conditions: frozenset[str]
    values: Allowed


@dataclass(frozen=True)
class Request:
    model: SubjectModel
    left: Expectation
    right: Expectation
    variants: tuple[tuple[Completion, Completion], ...]
    omega_complete: bool


@dataclass(frozen=True)
class CheckRecord:
    variant: int
    intersection: str
    state: str


@dataclass(frozen=True)
class Diagnostic:
    code: ErrorCode
    rule: str


@dataclass(frozen=True)
class Analysis:
    status: str
    classification: Classification | None
    complete: bool
    variants_checked: int
    variants_total: int | None
    observed_classes: tuple[Classification, ...]
    checks: tuple[CheckRecord, ...]
    explanation: str
    diagnostic: Diagnostic | None = None

    def to_dict(self) -> dict:
        return asdict(self)
