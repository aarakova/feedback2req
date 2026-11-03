from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import Field
from sqlalchemy import exists, func, or_, select

from feedback2req.api.routes import Actor, Tx, page
from feedback2req.api.schemas import ClosedModel
from feedback2req.errors import AppError
from feedback2req.persistence.models import FeedbackSource, ProductDocument, Project, ProjectAccess
from feedback2req.persistence.processing import (
    Attempt,
    Finding,
    FindingEvidence,
    Fragment,
    Run,
    Unit,
)
from feedback2req.processing.service import command, run_view
from feedback2req.projects.service import require_project

router = APIRouter(prefix="/api/v1/projects/{project_id}")
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


class InputRef(ClosedModel):
    kind: Literal["source", "document"]
    id: UUID
    state_id: UUID


class Start(ClosedModel):
    operation: Literal["inspect_text", "extract_feedback"]
    inputs: list[InputRef] = Field(min_length=1, max_length=32)


class Retry(ClosedModel):
    expected_attempt_id: UUID


@router.get("/overview")
def overview(project_id: UUID, tx: Tx, actor: Actor):
    sources = (
        select(func.count())
        .select_from(FeedbackSource)
        .where(
            FeedbackSource.project_id == Project.id,
            FeedbackSource.kind == "text",
            FeedbackSource.availability == "available",
        )
        .correlate(Project)
        .scalar_subquery()
    )
    documents = (
        select(func.count())
        .select_from(ProductDocument)
        .where(ProductDocument.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    latest = (
        select(Run.id)
        .where(Run.project_id == Project.id)
        .order_by(Run.created_at.desc(), Run.id.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    access = exists().where(
        ProjectAccess.project_id == Project.id, ProjectAccess.user_id == actor.user.id
    )
    row = tx.execute(
        select(Project.id, sources, documents, latest, func.statement_timestamp()).where(
            Project.id == project_id, or_(Project.owner_id == actor.user.id, access)
        )
    ).first()
    if row is None:
        raise AppError(404, "not_found", "Project or object not found")
    return {
        "project_id": row[0],
        "calculated_at": row[4],
        "material_counts": {"text_sources": row[1], "product_documents": row[2]},
        "semantic_metrics": {"availability": "not_implemented"},
        "processing": {"availability": "available", "latest_run_id": row[3]},
    }


@router.post("/runs", status_code=202)
def start(project_id: UUID, body: Start, tx: Tx, actor: Actor, key: Key):
    run = command(
        tx,
        project_id,
        actor.user.id,
        key,
        body.operation,
        [ref.model_dump() for ref in body.inputs],
    )
    return run_view(tx, run)


@router.get("/runs")
def runs(project_id: UUID, request: Request, tx: Tx, actor: Actor, cursor: UUID | None = None):
    require_project(tx, project_id, actor.user.id, write=True)
    query = select(Run).where(Run.project_id == project_id)
    if cursor:
        query = query.where(Run.id > cursor)
    limit = request.app.state.settings.page_size
    rows = tx.scalars(query.order_by(Run.id).limit(limit + 1)).all()
    return page([run_view(tx, row) for row in rows], limit, lambda row: row["id"])


@router.get("/runs/{run_id}")
def run(project_id: UUID, run_id: UUID, tx: Tx, actor: Actor):
    require_project(tx, project_id, actor.user.id, write=True)
    row = tx.scalar(select(Run).where(Run.project_id == project_id, Run.id == run_id))
    if row is None:
        raise AppError(404, "not_found", "Project or object not found")
    return run_view(tx, row)


@router.post("/units/{unit_id}/retries", status_code=202)
def retry(project_id: UUID, unit_id: UUID, body: Retry, tx: Tx, actor: Actor, key: Key):
    require_project(tx, project_id, actor.user.id, write=True)
    unit = tx.scalar(select(Unit).where(Unit.project_id == project_id, Unit.id == unit_id))
    if unit is None:
        raise AppError(404, "not_found", "Project or object not found")
    attempt = tx.scalar(select(Attempt).where(Attempt.unit_id == unit.id))
    if attempt is None or attempt.id != body.expected_attempt_id:
        raise AppError(409, "retry_not_allowed", "Expected failed attempt is required")
    from feedback2req.processing.service import input_ref

    ref = input_ref(unit)
    ref = {k: UUID(v) if k != "kind" else v for k, v in ref.items()}
    result = command(
        tx,
        project_id,
        actor.user.id,
        key,
        tx.get(Run, unit.run_id).operation,
        [ref],
        retry=attempt.id,
    )
    return run_view(tx, result)


def fragment_view(row):
    return {
        "id": row.id,
        "state_id": row.id,
        "attempt_id": row.attempt_id,
        "source_ref": {
            "kind": "feedback_source",
            "id": row.source_id,
            "state_id": row.source_state_id,
        },
        "text_ref": {
            "kind": "feedback_source",
            "id": row.source_id,
            "state_id": row.source_state_id,
        },
        "quote": row.quote,
        "locator": {"start": row.start, "end": row.end},
        "reliability": row.reliability,
    }


def finding_view(tx, row):
    attempt = tx.get(Attempt, row.attempt_id)
    fragments = tx.scalars(
        select(Fragment)
        .join(FindingEvidence, FindingEvidence.fragment_id == Fragment.id)
        .where(FindingEvidence.finding_id == row.id, FindingEvidence.project_id == row.project_id)
    ).all()
    current = all(
        tx.scalar(
            select(FeedbackSource.current_state_id).where(
                FeedbackSource.project_id == row.project_id, FeedbackSource.id == fragment.source_id
            )
        )
        == fragment.source_state_id
        for fragment in fragments
    )
    return {
        "id": row.id,
        "state_id": row.id,
        "text": row.text,
        "types": row.types,
        "mode": row.mode,
        "authorship": "ai",
        "synthetic": attempt.synthetic,
        "attempt_id": attempt.id,
        "created_at": row.created_at,
        "freshness": "current" if current else "requires_update",
        "evidence": [fragment_view(fragment) for fragment in fragments],
        "coverage": attempt.coverage,
        "annotations": attempt.annotations,
        "provider": attempt.provider,
        "model": attempt.model,
        "ai_performed": attempt.ai_performed,
    }


@router.get("/findings")
def findings(
    project_id: UUID,
    request: Request,
    tx: Tx,
    actor: Actor,
    cursor: UUID | None = None,
    attempt_id: UUID | None = None,
):
    require_project(tx, project_id, actor.user.id, write=True)
    query = select(Finding).where(Finding.project_id == project_id)
    if cursor:
        query = query.where(Finding.id > cursor)
    if attempt_id:
        query = query.where(Finding.attempt_id == attempt_id)
    limit = request.app.state.settings.page_size
    rows = tx.scalars(query.order_by(Finding.id).limit(limit + 1)).all()
    return page([finding_view(tx, row) for row in rows], limit, lambda row: row["id"])


@router.get("/findings/{finding_id}")
def finding(project_id: UUID, finding_id: UUID, tx: Tx, actor: Actor):
    require_project(tx, project_id, actor.user.id, write=True)
    row = tx.scalar(
        select(Finding).where(Finding.project_id == project_id, Finding.id == finding_id)
    )
    if row is None:
        raise AppError(404, "not_found", "Project or object not found")
    return finding_view(tx, row)


@router.get("/fragments/{fragment_id}/states/{state_id}")
def fragment(project_id: UUID, fragment_id: UUID, state_id: UUID, tx: Tx, actor: Actor):
    require_project(tx, project_id, actor.user.id)
    row = tx.scalar(
        select(Fragment).where(
            Fragment.project_id == project_id, Fragment.id == fragment_id, Fragment.id == state_id
        )
    )
    if row is None:
        raise AppError(404, "not_found", "Project or object not found")
    return fragment_view(row)
