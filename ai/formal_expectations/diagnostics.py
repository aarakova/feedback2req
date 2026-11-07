"""Safe, typed failures: none of these is semantic uncertainty U."""

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    INVALID_FORMALIZATION = "invalid_formalization"
    NOT_COMPARABLE = "not_comparable"
    UNSUPPORTED_INPUT = "unsupported_input"
    INCOMPLETE_OMEGA = "incomplete_omega"
    RESOURCE_LIMIT = "resource_limit"
    SOLVER_UNKNOWN = "solver_unknown"
    TIMEOUT = "timeout"
    SOLVER_FAILURE = "solver_failure"
    INTERNAL_FAILURE = "internal_failure"


class FormalError(Exception):
    def __init__(self, code: ErrorCode, rule: str):
        self.code = code
        self.rule = rule
        super().__init__(f"{code}:{rule}")
