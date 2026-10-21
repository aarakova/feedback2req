import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from feedback2req.api.schemas import (
    AccessChange,
    Credentials,
    LoginCredentials,
    ProjectName,
    project_view,
    user_view,
)
from feedback2req.errors import AppError
from feedback2req.identity.service import Principal
from feedback2req.projects import service as projects

router = APIRouter(prefix="/api/v1")


def transaction(request: Request):
    with request.app.state.sessions.begin() as tx:
        yield tx


Tx = Annotated[Session, Depends(transaction, scope="function")]


def current(request: Request, tx: Tx):
    settings = request.app.state.settings
    principal = request.app.state.identity.authenticate(
        tx, request.cookies.get(settings.session_cookie)
    )
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(csrf.encode(), principal.session.csrf_secret.encode()):
            raise AppError(403, "csrf_rejected", "Valid CSRF token is required")
    return principal


Actor = Annotated[Principal, Depends(current)]


def page(items, limit, key):
    more = len(items) > limit
    items = items[:limit]
    return {"items": items, "next_cursor": str(key(items[-1])) if more else None}


@router.post("/auth/register", status_code=201)
def register(body: Credentials, request: Request, tx: Tx):
    return user_view(
        request.app.state.identity.register(
            tx,
            body.login,
            body.password.get_secret_value(),
        )
    )


@router.post("/auth/session")
def login(body: LoginCredentials, request: Request, response: Response, tx: Tx):
    principal, raw_token = request.app.state.identity.login(
        tx,
        body.login,
        body.password.get_secret_value(),
    )
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie,
        raw_token,
        max_age=settings.session_seconds,
        httponly=True,
        secure=settings.allowed_origin.startswith("https://"),
        samesite="lax",
        path="/",
    )
    return {"user": user_view(principal.user), "csrf_token": principal.session.csrf_secret}


@router.get("/auth/session")
def get_session(actor: Actor):
    return {"user": user_view(actor.user), "csrf_token": actor.session.csrf_secret}


@router.delete("/auth/session", status_code=204)
def logout(request: Request, response: Response, tx: Tx, actor: Actor):
    request.app.state.identity.logout(tx, actor)
    settings = request.app.state.settings
    response.delete_cookie(
        settings.session_cookie,
        path="/",
        secure=settings.allowed_origin.startswith("https://"),
        httponly=True,
        samesite="lax",
    )


@router.post("/projects", status_code=201)
def create_project(body: ProjectName, tx: Tx, actor: Actor):
    project = projects.create_project(tx, actor.user.id, body.name)
    return project_view(project, projects.permissions(project, actor.user.id, None))


@router.get("/projects")
def list_projects(request: Request, tx: Tx, actor: Actor, cursor: UUID | None = None):
    limit = request.app.state.settings.page_size
    rows = projects.list_projects(tx, actor.user.id, cursor, limit)
    items = []
    for project in rows:
        _, access = projects.require_project(tx, project.id, actor.user.id)
        items.append(project_view(project, projects.permissions(project, actor.user.id, access)))
    return page(items, limit, lambda item: item["id"])


@router.get("/projects/{project_id}")
def get_project(project_id: UUID, tx: Tx, actor: Actor):
    project, access = projects.require_project(tx, project_id, actor.user.id)
    return project_view(project, projects.permissions(project, actor.user.id, access))


@router.patch("/projects/{project_id}")
def rename_project(project_id: UUID, body: ProjectName, tx: Tx, actor: Actor):
    project, access = projects.rename_project(tx, project_id, actor.user.id, body.name)
    return project_view(project, projects.permissions(project, actor.user.id, access))


@router.get("/projects/{project_id}/access")
def list_access(
    project_id: UUID,
    request: Request,
    tx: Tx,
    actor: Actor,
    cursor: Annotated[UUID | None, Query()] = None,
):
    limit = request.app.state.settings.page_size
    rows = projects.list_access(tx, project_id, actor.user.id, cursor, limit)
    return page(rows, limit, lambda item: item["user_id"])


@router.put("/projects/{project_id}/access/{user_id}")
def set_access(project_id: UUID, user_id: UUID, body: AccessChange, tx: Tx, actor: Actor):
    return projects.set_access(tx, project_id, actor.user.id, user_id, body.can_approve)


@router.delete("/projects/{project_id}/access/{user_id}", status_code=204)
def delete_access(project_id: UUID, user_id: UUID, tx: Tx, actor: Actor):
    projects.remove_access(tx, project_id, actor.user.id, user_id)
