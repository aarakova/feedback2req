"""Translation of validated sets to separate, domain-bounded Z3 queries."""

import z3

from .diagnostics import ErrorCode, FormalError
from .limits import Budget
from .model import Allowed, Completion, SatState, SubjectModel


class Engine:
    def __init__(self, model: SubjectModel, budget: Budget):
        self.model = model
        self.budget = budget
        # No shared global context or global solver parameter mutations.
        self.ctx = z3.Context()

    def _real(self, value):
        return z3.RealVal(f"{value.numerator}/{value.denominator}", ctx=self.ctx)

    def _constraint(self, var, allowed: Allowed, members: tuple):
        if allowed.kind == "interval":
            return z3.And(var >= self._real(allowed.lower), var <= self._real(allowed.upper))
        if allowed.kind == "boolean":
            return z3.Or([var == z3.BoolVal(v, self.ctx) for v in sorted(allowed.members)])
        return z3.Or([var == members.index(v) for v in sorted(allowed.members)])

    def intersection(self, left: Completion, right: Completion, kind: str) -> SatState:
        timeout = self.budget.solver_time()
        solver = z3.Solver(ctx=self.ctx)
        solver.set(
            timeout=timeout,
            rlimit=self.budget.limits.solver_rlimit,
            max_memory=self.budget.limits.solver_memory_mb,
            random_seed=0,
        )
        if kind == "conditions":
            var = z3.Int("situation", ctx=self.ctx)
            universe = self.model.situations
            solver.add(var >= 0, var < len(universe))
            for completion in (left, right):
                solver.add(z3.Or([var == universe.index(v) for v in sorted(completion.conditions)]))
        else:
            domain = self.model.domain.values
            members = tuple(sorted(domain.members))
            if domain.kind == "interval":
                var = z3.Real("value", ctx=self.ctx)
            elif domain.kind == "boolean":
                var = z3.Bool("value", ctx=self.ctx)
            else:
                var = z3.Int("value", ctx=self.ctx)
            # Domain predicates apply even when the intersections seem obvious.
            solver.add(self._constraint(var, domain, members))
            solver.add(self._constraint(var, left.values, members))
            solver.add(self._constraint(var, right.values, members))
        # Translation also consumes the overall budget. Refresh immediately
        # before entering native check rather than granting an outdated timeout.
        solver.set(timeout=min(timeout, self.budget.remaining_ms()))
        result = solver.check()
        self.budget.remaining_ms()
        if result == z3.sat:
            return SatState.SAT
        if result == z3.unsat:
            return SatState.UNSAT
        reason = solver.reason_unknown().lower()
        if "timeout" in reason:
            raise FormalError(ErrorCode.TIMEOUT, "solver_timeout")
        if any(token in reason for token in ("resource", "memory", "memout", "rlimit")):
            raise FormalError(ErrorCode.RESOURCE_LIMIT, "solver_resources")
        raise FormalError(ErrorCode.SOLVER_UNKNOWN, "solver_unknown")
