from feedback2req.errors import AppError
from feedback2req.persistence.materials import MaterialRepository
from feedback2req.projects.service import require_project


def validate_text(value: str, limit: int):
    if len(value) > limit:
        raise AppError(413, "text_too_large", "Material text limit exceeded")
    if not value.strip() or "\x00" in value:
        raise AppError(422, "invalid_text", "Nonblank PostgreSQL-compatible text is required")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise AppError(422, "invalid_text", "Valid Unicode text is required") from None


def create(tx, actor_id, project_id, text, limit, *, title=None):
    require_project(tx, project_id, actor_id, write=True)
    validate_text(text, limit)
    if title is not None:
        validate_text(title, 200)
    return MaterialRepository(tx).create(project_id, actor_id, text, title=title)


def read(tx, actor_id, project_id, material_id, *, document=False):
    require_project(tx, project_id, actor_id)
    material = MaterialRepository(tx).get(project_id, material_id, document=document)
    if material is None:
        raise AppError(404, "not_found", "Project or object not found")
    return material


def list_materials(tx, actor_id, project_id, cursor, limit, *, document=False):
    require_project(tx, project_id, actor_id)
    return MaterialRepository(tx).list(project_id, cursor, limit, document=document)
