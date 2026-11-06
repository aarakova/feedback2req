from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import select

from feedback2req.api.routes import Actor, Tx, page
from feedback2req.grouping.views import group_detail, group_summary
from feedback2req.persistence.grouping import FindingGroup, GroupState
from feedback2req.projects.service import require_project

router = APIRouter(prefix="/api/v1/projects/{project_id}/groups")


@router.get("")
def groups(
    project_id: UUID,
    request: Request,
    tx: Tx,
    actor: Actor,
    cursor: UUID | None = None,
    attempt_id: UUID | None = None,
):
    require_project(tx, project_id, actor.user.id, write=True)
    query = (
        select(GroupState)
        .join(
            FindingGroup,
            (
                (FindingGroup.project_id == GroupState.project_id)
                & (FindingGroup.id == GroupState.group_id)
                & (FindingGroup.current_state_id == GroupState.id)
            ),
        )
        .where(GroupState.project_id == project_id)
    )
    if cursor:
        query = query.where(GroupState.group_id > cursor)
    if attempt_id:
        query = query.where(GroupState.attempt_id == attempt_id)
    limit = request.app.state.settings.page_size
    states = tx.scalars(query.order_by(GroupState.group_id).limit(limit + 1)).all()
    return page([group_summary(tx, s) for s in states], limit, lambda s: s["id"])


@router.get("/{group_id}")
def group(project_id: UUID, group_id: UUID, tx: Tx, actor: Actor):
    require_project(tx, project_id, actor.user.id, write=True)
    return group_detail(tx, project_id, group_id)


@router.get("/{group_id}/states/{state_id}")
def group_state(project_id: UUID, group_id: UUID, state_id: UUID, tx: Tx, actor: Actor):
    require_project(tx, project_id, actor.user.id, write=True)
    return group_detail(tx, project_id, group_id, state_id)
