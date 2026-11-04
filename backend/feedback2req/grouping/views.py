"""Exact saved group states and dependencies; list summaries contain no source text."""

from sqlalchemy import select

from feedback2req.errors import AppError
from feedback2req.grouping.service import rows, state_ref
from feedback2req.persistence.grouping import (
    ConflictPosition,
    FindingGroup,
    GroupConflict,
    GroupContext,
    GroupingDocument,
    GroupingInput,
    GroupingPreviousGroup,
    GroupMember,
    GroupScope,
    GroupState,
    PositionMember,
)
from feedback2req.persistence.models import ProductDocument
from feedback2req.persistence.processing import Attempt, Finding
from feedback2req.processing.views import finding_view


def dependencies(tx, model, state):
    return tx.scalars(
        select(model).where(
            model.project_id == state.project_id,
            model.group_state_id == state.id,
        )
    ).all()


def group_summary(tx, state, visited=None):
    attempt = tx.get(Attempt, state.attempt_id) if state.attempt_id else None
    current = True
    for item in dependencies(tx, GroupScope, state):
        finding = tx.scalar(
            select(Finding).where(
                Finding.project_id == state.project_id,
                Finding.id == item.finding_id,
            )
        )
        current = (
            current and finding is not None and finding_view(tx, finding)["freshness"] == "current"
        )
    for item in dependencies(tx, GroupContext, state):
        current = (
            current
            and tx.scalar(
                select(ProductDocument.current_state_id).where(
                    ProductDocument.project_id == state.project_id,
                    ProductDocument.id == item.document_id,
                )
            )
            == item.document_state_id
        )
    # Previous groups are trusted context, never permission to overwrite their current state.
    visited = set() if visited is None else set(visited)
    if state.id in visited:
        current = False
    elif attempt:
        visited.add(state.id)
        for item in tx.scalars(
            select(GroupingPreviousGroup).where(
                GroupingPreviousGroup.project_id == state.project_id,
                GroupingPreviousGroup.unit_id == attempt.unit_id,
            )
        ):
            header = tx.get(FindingGroup, item.group_id)
            prior = tx.get(GroupState, item.group_state_id)
            current = (
                current and header is not None and header.current_state_id == item.group_state_id
            )
            current = (
                current
                and prior is not None
                and group_summary(tx, prior, visited)["freshness"] == "current"
            )
    return {
        "id": state.group_id,
        "state_id": state.id,
        "title": state.title,
        "summary": state.summary,
        "authorship": state.authorship,
        "synthetic": attempt.synthetic if attempt else False,
        "attempt_id": state.attempt_id,
        "created_at": state.created_at,
        "freshness": "current" if current else "requires_update",
    }


def group_detail(tx, project_id, group_id, state_id=None):
    header = tx.scalar(
        select(FindingGroup).where(
            FindingGroup.project_id == project_id,
            FindingGroup.id == group_id,
        )
    )
    if header is None:
        raise AppError(404, "not_found", "Project or object not found")
    state = tx.scalar(
        select(GroupState).where(
            GroupState.project_id == project_id,
            GroupState.group_id == group_id,
            GroupState.id == (state_id if state_id is not None else header.current_state_id),
        )
    )
    if state is None:
        raise AppError(404, "not_found", "Project or object not found")
    result = group_summary(tx, state)
    attempt = tx.get(Attempt, state.attempt_id) if state.attempt_id else None
    members = []
    for item in sorted(dependencies(tx, GroupMember, state), key=lambda r: r.finding_id):
        finding = tx.scalar(
            select(Finding).where(
                Finding.project_id == project_id,
                Finding.id == item.finding_id,
            )
        )
        members.append(
            {
                "ref": state_ref("finding", item.finding_id, item.finding_state_id),
                "finding": finding_view(tx, finding),
            }
        )
    conflicts = []
    for conflict in sorted(dependencies(tx, GroupConflict, state), key=lambda r: r.id):
        positions = []
        for pos in tx.scalars(
            select(ConflictPosition)
            .where(
                ConflictPosition.project_id == project_id,
                ConflictPosition.group_state_id == state.id,
                ConflictPosition.conflict_id == conflict.id,
            )
            .order_by(ConflictPosition.ordinal)
        ):
            finding_refs = [
                state_ref("finding", m.finding_id, m.finding_state_id)
                for m in tx.scalars(
                    select(PositionMember)
                    .where(
                        PositionMember.project_id == project_id,
                        PositionMember.group_state_id == state.id,
                        PositionMember.position_id == pos.id,
                    )
                    .order_by(PositionMember.finding_id)
                )
            ]
            positions.append(
                {"id": pos.id, "description": pos.description, "findings": finding_refs}
            )
        conflicts.append(
            {"id": conflict.id, "description": conflict.description, "positions": positions}
        )
    result.update(
        {
            "previous_state_id": state.previous_state_id,
            "author_id": state.author_id,
            "members": members,
            "conflicts": conflicts,
            "considered_findings": [
                state_ref("finding", v.finding_id, v.finding_state_id)
                for v in sorted(dependencies(tx, GroupScope, state), key=lambda r: r.finding_id)
            ],
            "context": [
                {
                    "ref": state_ref("product_document", v.document_id, v.document_state_id),
                    "locator": {"start": v.start, "end": v.end},
                }
                for v in dependencies(tx, GroupContext, state)
            ],
            "coverage": attempt.coverage if attempt else [],
            "annotations": attempt.annotations
            if attempt
            else {"questions": [], "uncertainties": []},
            "provider": attempt.provider if attempt else None,
            "model": attempt.model if attempt else None,
            "ai_performed": attempt.ai_performed if attempt else False,
        }
    )
    return result


def unit_input(tx, unit):
    return {
        "kind": "finding_set",
        "findings": [
            state_ref("finding", r.finding_id, r.finding_state_id)
            for r in rows(tx, GroupingInput, unit)
        ],
        "documents": [
            state_ref("product_document", r.document_id, r.document_state_id)
            for r in rows(tx, GroupingDocument, unit)
        ],
        "previous_groups": [
            state_ref("finding_group", r.group_id, r.group_state_id)
            for r in rows(tx, GroupingPreviousGroup, unit)
        ],
    }


def attempt_result(tx, unit, attempt):
    if attempt.ungrouped_findings is None:
        return None
    return {
        "group_ids": list(
            tx.scalars(
                select(GroupState.group_id)
                .where(
                    GroupState.project_id == unit.project_id,
                    GroupState.attempt_id == attempt.id,
                )
                .order_by(GroupState.group_id)
            )
        ),
        "ungrouped_findings": attempt.ungrouped_findings,
        "input_findings": [
            {"key": r.key, "ref": state_ref("finding", r.finding_id, r.finding_state_id)}
            for r in rows(tx, GroupingInput, unit)
        ],
    }
