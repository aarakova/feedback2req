from uuid import UUID

from sqlalchemy.orm import Session

from feedback2req.errors import AppError
from feedback2req.persistence.models import Project, ProjectAccess
from feedback2req.persistence.projects import ProjectRepository


def permissions(project: Project, user_id: UUID, access: ProjectAccess | None):
    owner = project.owner_id == user_id
    return {
        "is_owner": owner,
        "is_member": owner or access is not None,
        "can_approve": owner or bool(access and access.can_approve),
    }


def require_project(tx: Session, project_id: UUID, user_id: UUID, *, owner=False, write=False):
    repo = ProjectRepository(tx)
    project = repo.get(project_id, for_update=write)
    access = repo.access(project_id, user_id) if project else None
    if project is None or (project.owner_id != user_id and access is None):
        raise AppError(404, "not_found", "Project or object not found")
    if owner and project.owner_id != user_id:
        raise AppError(403, "forbidden", "Project owner permission is required")
    return project, access


def create_project(tx: Session, user_id: UUID, name: str):
    return ProjectRepository(tx).create(user_id, name)


def list_projects(tx: Session, user_id: UUID, cursor: UUID | None, limit: int):
    return ProjectRepository(tx).list_for_user(user_id, cursor, limit)


def rename_project(tx: Session, project_id: UUID, user_id: UUID, name: str):
    project, access = require_project(tx, project_id, user_id, owner=True, write=True)
    ProjectRepository(tx).rename(project, name)
    return project, access


def set_access(tx: Session, project_id: UUID, actor_id: UUID, target_id: UUID, can_approve: bool):
    project, _ = require_project(tx, project_id, actor_id, owner=True, write=True)
    protect_owner(project, target_id)
    repo = ProjectRepository(tx)
    if not repo.registered_user(target_id):
        raise AppError(422, "invalid_user", "Registered user is required")
    repo.set_access(project_id, target_id, can_approve)
    return {"user_id": target_id, "is_owner": False, "is_member": True, "can_approve": can_approve}


def remove_access(tx: Session, project_id: UUID, actor_id: UUID, target_id: UUID):
    project, _ = require_project(tx, project_id, actor_id, owner=True, write=True)
    protect_owner(project, target_id)
    ProjectRepository(tx).remove_access(project_id, target_id)


def protect_owner(project: Project, target_id: UUID):
    if project.owner_id == target_id:
        raise AppError(409, "owner_access_immutable", "Owner permissions cannot be changed")


def list_access(tx: Session, project_id: UUID, actor_id: UUID, cursor: UUID | None, limit: int):
    project, _ = require_project(tx, project_id, actor_id, owner=True)
    # The owner is a computed participant; there is no revocable owner access row.
    rows = ProjectRepository(tx).list_access(project_id, project.owner_id, cursor, limit)
    return [
        {
            "user_id": row[0],
            "is_owner": row[0] == project.owner_id,
            "is_member": True,
            "can_approve": bool(row[1]),
        }
        for row in rows
    ]
