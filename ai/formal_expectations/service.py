"""Exhaustive finite Ω analysis; never publish a class after a failed check."""

import z3

from .diagnostics import ErrorCode, FormalError
from .limits import Budget, Limits
from .model import Analysis, CheckRecord, Classification, Diagnostic, SatState
from .solver import Engine
from .validation import parse_request

EXPLANATIONS = {
    Classification.D: "Every admissible refinement has disjoint application conditions.",
    Classification.K: "Every admissible refinement overlaps in conditions and has disjoint values.",
    Classification.S: "Every admissible refinement overlaps in both conditions and values.",
    Classification.U: (
        "Admissible refinements yield different classes; semantic uncertainty remains."
    ),
}


def _technical(error: Exception) -> Diagnostic:
    if isinstance(error, FormalError):
        return Diagnostic(error.code, error.rule)
    if isinstance(error, MemoryError | z3.Z3Exception):
        # A native exception may disclose input; keep only a fixed diagnostic.
        if isinstance(error, MemoryError):
            return Diagnostic(ErrorCode.RESOURCE_LIMIT, "memory_exhausted")
        return Diagnostic(ErrorCode.SOLVER_FAILURE, "solver_exception")
    if isinstance(error, TimeoutError):
        return Diagnostic(ErrorCode.TIMEOUT, "solver_timeout")
    return Diagnostic(ErrorCode.INTERNAL_FAILURE, "unexpected_failure")


def analyze(data: dict | str | bytes, *, limits: Limits | None = None) -> Analysis:
    """Analyze independent atomic expectations in the explicitly supplied model.

    JSON format version 1 is local to this component, not an AI contract version.
    Failure results always have classification=None and complete=False.
    """
    checks = []
    observed = set()
    checked, total = 0, None
    try:
        budget = Budget(limits if limits is not None else Limits())
        request = parse_request(data, budget)
        total = len(request.variants)
        if not request.omega_complete:
            raise FormalError(ErrorCode.INCOMPLETE_OMEGA, "omega_not_declared_complete")
        engine = Engine(request.model, budget)
        for index, (left, right) in enumerate(request.variants):
            states = []
            for kind in ("conditions", "values"):
                try:
                    state = engine.intersection(left, right, kind)
                except Exception as error:  # noqa: BLE001 -- sanitize solver boundary.
                    diagnostic = _technical(error)
                    checks.append(CheckRecord(index, kind, diagnostic.code.value))
                    raise
                checks.append(CheckRecord(index, kind, state.value))
                states.append(state)
            relation = (
                Classification.D
                if states[0] == SatState.UNSAT
                else Classification.K
                if states[1] == SatState.UNSAT
                else Classification.S
            )
            observed.add(relation)
            checked += 1
        budget.remaining_ms()
        relation = next(iter(observed)) if len(observed) == 1 else Classification.U
        return Analysis(
            "classified",
            relation,
            True,
            checked,
            total,
            tuple(sorted(observed)),
            tuple(checks),
            EXPLANATIONS[relation],
        )
    except Exception as error:  # noqa: BLE001 -- public boundary must not leak input text.
        return Analysis(
            "failed",
            None,
            False,
            checked,
            total,
            tuple(sorted(observed)),
            tuple(checks),
            "No classification is established; inspect the diagnostic.",
            _technical(error),
        )
