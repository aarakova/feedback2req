"""Internal PostgreSQL queue using the existing single-attempt lifecycle."""

import hashlib
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from feedback2req.errors import AppError
from feedback2req.grouping.execution import execute_prepared_grouping
from feedback2req.grouping.service import Provenance, build_request, current
from feedback2req.persistence.processing import Attempt, Run, Unit
from feedback2req.processing.service import DEADLINE, LEASE, end, locked, now, recover_one


def claim_grouping(sessions, provenance):
    if not isinstance(provenance, Provenance):
        raise ValueError("Explicit worker provenance required")
    with sessions.begin() as tx:
        unit_id = tx.scalar(
            select(Unit.id)
            .join(Run, Run.id == Unit.run_id)
            .where(
                Unit.state == "queued",
                Unit.input_kind == "finding_set",
                Run.operation == "group_findings",
            )
            .order_by(Unit.created_at, Unit.id)
            .limit(1)
        )
        pair = locked(tx, unit_id) if unit_id else None
        if pair is None or pair[0].state != "queued":
            return None
        unit, existing = pair
        if existing is not None:
            raise RuntimeError("Queued grouping already has an attempt")
        instant, token = now(tx), uuid4()
        attempt = Attempt(
            id=uuid4(),
            project_id=unit.project_id,
            unit_id=unit.id,
            state="running",
            owner_token=token,
            grouping_owner_hash=hashlib.sha256(token.bytes).hexdigest(),
            started_at=instant,
            deadline_at=instant + timedelta(seconds=DEADLINE),
            lease_expires_at=instant + timedelta(seconds=LEASE),
            provider=provenance.provider,
            model=provenance.model,
            synthetic=provenance.synthetic,
            ai_performed=False if provenance.synthetic else None,
        )
        tx.add(attempt)
        unit.state = "running"
        tx.flush()
        try:
            current(tx, unit)
        except AppError:
            end(tx, unit, attempt, "cancelled", "access_revoked", token)
            return None
        try:
            request = build_request(tx, unit, attempt)
        except AppError:
            end(tx, unit, attempt, "cancelled", "input_changed", token)
            return None
        return {
            "run_id": unit.run_id,
            "unit_id": unit.id,
            "attempt_id": attempt.id,
            "owner_token": token,
            "request": request,
            "replayed": False,
        }
    # No capability escapes without a confirmed commit; uncertainty stops the pass.


def execute_queued_grouping(sessions, provider):
    recover_one(sessions)
    provenance = Provenance(provider.name, provider.model, provider.synthetic)
    handle = claim_grouping(sessions, provenance)
    if handle is None:
        return False
    execute_prepared_grouping(sessions, handle, provider)
    return True
