"""Local technical budgets, separate from the mathematical input."""

from dataclasses import dataclass, fields
from time import monotonic

from .diagnostics import ErrorCode, FormalError


@dataclass(frozen=True)
class Limits:
    max_variants: int = 256
    max_solver_calls: int = 512
    total_timeout_ms: int = 5000
    solver_timeout_ms: int = 1000
    solver_rlimit: int = 100_000
    solver_memory_mb: int = 128
    max_input_bytes: int = 1_048_576

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 1 <= value <= 2_147_483_647:
                raise ValueError(f"{field.name} must be a positive 32-bit integer")


class Budget:
    def __init__(self, limits: Limits):
        self.limits = limits
        self.deadline = monotonic() + limits.total_timeout_ms / 1000
        self.calls = 0

    def remaining_ms(self) -> int:
        remaining = int((self.deadline - monotonic()) * 1000)
        if remaining <= 0:
            raise FormalError(ErrorCode.TIMEOUT, "total_deadline")
        return remaining

    def solver_time(self) -> int:
        self.remaining_ms()
        if self.calls >= self.limits.max_solver_calls:
            raise FormalError(ErrorCode.RESOURCE_LIMIT, "solver_calls")
        self.calls += 1
        return min(self.remaining_ms(), self.limits.solver_timeout_ms)
